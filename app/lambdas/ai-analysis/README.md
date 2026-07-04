this is a lambda to retrieve last 1-minute market data over last 1 hour and invoke LLM model for analysis

Testing
* `pytest -s -m manual` - trigger real integration test
* `pytest` - run all tests (exclude the real integration test)