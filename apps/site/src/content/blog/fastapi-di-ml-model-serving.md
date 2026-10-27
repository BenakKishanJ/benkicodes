---
title: 'FastAPI DI for ML Model Serving: Caching & Injection'
description: Learn how to use FastAPI's Dependency Injection system to load large ML models once, cache them, and inject them into endpoints efficiently.
pubDate: &id001 2026-10-28
lastReviewed: *id001
tags:
- fastapi
- machine-learning
- dependency-injection
- ai-engineering
category: guide
draft: false
featured: false
sources:
- title: Dependencies¶
  url: https://fastapi.tiangolo.com/tutorial/dependencies/
  accessed: *id001
aiAssisted: true
reviewedBy: Ben
pipelineRunId: feeb0509e2
---

## Why Dependency Injection Matters for ML Serving

You can use FastAPI's dependency injection to load an ML model once and reuse it across requests, avoiding the performance hit of reloading it each time. This article walks you through a worked example, from writing a dependency function to caching the model and injecting it into your endpoints.

ML models are expensive to load. The process involves disk I/O to read the file, memory allocation to deserialize the object, and sometimes additional computation to initialize the model. Doing this on every request adds significant latency and wastes server resources. [\[1\]](#sources-h) FastAPI's dependency injection system helps here: you define the scope of the dependency yourself — with a global cache or an application startup event, for example — so the model loads only once, and the DI system then injects the result into any path operation that needs it. [\[1\]](#sources-h) This pattern promotes shared logic and minimizes code repetition, making it ideal for model loading, database connections, or authentication. [\[1\]](#sources-h) Instead of writing the same loading code in every endpoint, you define it once in a dependency and reuse it across your application. The DI system also integrates with FastAPI's OpenAPI documentation, so your dependencies are automatically documented.

## Building a Model Dependency (The 'Dependable')

In FastAPI, a dependency is simply a function. It can be synchronous or asynchronous, and it can accept the same parameters as a path operation function, such as query parameters, headers, or request bodies. [\[1\]](#sources-h) For an ML model, you might start with a straightforward function that loads the model from disk using pickle:

```python
import pickle

def get_model():
    return pickle.load(open('model.pkl', 'rb'))
```

Note that `pickle.load` is a synchronous I/O operation and can block the FastAPI event loop. For large models, consider wrapping the load with `run_in_threadpool` or running it in a separate process.

This function returns the loaded model object. However, there's a critical issue: every time FastAPI calls this dependency, it reloads the model from disk. That means each request triggers a full load, which is exactly what you want to avoid. [\[1\]](#sources-h) The dependency is called for each request that depends on it, so without caching, you're back to the original problem. If your model loading involves I/O-bound operations, you could define the dependency as async to avoid blocking the server during loading, but caching is still essential to prevent repeated loads. The key is that the dependency function is just a callable that returns the model—it doesn't have to be complex.

## Avoiding the Reload Mistake: Caching the Model

The naive approach above re-reads the model file for every request, causing high latency and wasted resources. [\[1\]](#sources-h) To fix this, you need to cache the model so it loads only once. Python's `functools.lru_cache` decorator provides a simple, thread-safe way to cache the result of a function:

```python
import pickle
from functools import lru_cache

@lru_cache
def get_model():
    return pickle.load(open('model.pkl', 'rb'))
```

With this decorator, `get_model()` runs only the first time it's called. Subsequent calls return the cached result, avoiding redundant disk reads. [\[1\]](#sources-h) This approach is thread-safe for read-only models because `lru_cache` uses a lock internally. Alternatively, you could use a global variable or a singleton class, but `lru_cache` is cleaner and integrates well with FastAPI's dependency system. [\[1\]](#sources-h) For more control, you could also use a custom caching mechanism, such as a dictionary with expiration, but for most ML serving cases, `lru_cache` is sufficient. It also works with multiple model versions by passing different arguments to the function, since `lru_cache` caches based on arguments.

## Injecting the Model into Path Operations

With the cached dependency ready, you can inject it into your endpoints using `Depends`. FastAPI automatically calls the dependency and provides the result to your path operation function. [\[1\]](#sources-h) Here's how to set it up:

```python
from fastapi import Depends, FastAPI
from typing import Annotated

app = FastAPI()

# Define a type alias for the model dependency
ModelDep = Annotated[YourModelType, Depends(get_model)]

@app.post("/predict")
async def predict(input: InputData, model: ModelDep):
    return model.predict(input)
```

In this example, FastAPI calls `get_model()` once (thanks to caching) and injects the model into the `predict` function. [\[1\]](#sources-h) The `Annotated` type alias reduces duplication—you can reuse `ModelDep` across multiple endpoints without repeating the `Depends` call. [\[1\]](#sources-h) This keeps your code DRY and makes it easy to swap dependencies if needed. You can also use the older syntax without `Annotated`, but `Annotated` is now recommended for better type hints. [\[1\]](#sources-h)

You can also create multiple endpoints that use the same model dependency:

```python
@app.post("/predict")
async def predict(input: InputData, model: ModelDep):
    return model.predict(input)

@app.post("/predict-batch")
async def predict_batch(inputs: List[InputData], model: ModelDep):
    return [model.predict(inp) for inp in inputs]
```

Both endpoints share the same cached model instance, loaded only once at the first request. This pattern also integrates with FastAPI's OpenAPI documentation, as the dependency is automatically documented. [\[1\]](#sources-h)

## Extending the Pattern: Sub-Dependencies for Preprocessing

Dependencies can depend on other dependencies, forming a hierarchical tree. FastAPI resolves all sub-dependencies automatically. [\[1\]](#sources-h) This is useful for preprocessing steps like tokenization or feature extraction before model inference. For example, you might have a tokenizer that needs to be loaded and a preprocessing step that uses it:

```python
from fastapi import Body

def get_tokenizer():
    # Load or create a tokenizer
    return tokenizer

def get_preprocessed_input(
    raw_data: Annotated[InputData, Body()],
    tokenizer: Annotated[Tokenizer, Depends(get_tokenizer)]
):
    # Preprocess the raw data using the tokenizer
    return preprocessed_data

@app.post("/predict")
async def predict(data: Annotated[PreprocessedData, Depends(get_preprocessed_input)], model: ModelDep):
    return model.predict(data)
```

Here, `get_preprocessed_input` explicitly declares the raw request body with `Body()` and depends on `get_tokenizer`. The path operation only declares the top-level dependency. FastAPI resolves `get_tokenizer` first, then calls `get_preprocessed_input` with the tokenizer and the parsed request body. [\[1\]](#sources-h) This pattern keeps your code modular and testable—you can swap out the tokenizer or preprocessing logic without changing the endpoint code.

You can also combine this with model caching. For instance, you might have a sub-dependency that loads the model and another that preprocesses the input, then inject both into the endpoint. FastAPI's DI system makes this straightforward by allowing you to define dependencies that depend on others.

## Key Takeaways

- Use FastAPI's dependency injection to load ML models once via caching and inject them into endpoints—never reload per request. [\[1\]](#sources-h)
- Dependencies are simple functions that can be async or sync, and they automatically integrate with OpenAPI documentation. [\[1\]](#sources-h)
- Chain dependencies for preprocessing, authentication, or database connections to keep your code modular and testable. [\[1\]](#sources-h)
- The `lru_cache` decorator is a simple, thread-safe way to cache your model dependency.
