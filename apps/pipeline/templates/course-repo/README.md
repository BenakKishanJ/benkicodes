# Project setup: run with uv
uv sync                      # create .venv and install dependencies
uv add <package>             # named by a part; resolved versions only
uv run pytest                # run the tests (no network: fake LLM)

# Follow along
git clone https://github.com/__GITHUB__/__NAME__.git
git checkout part-N                                  # any published part
git diff part-(N-1) part-N                           # what part N adds
