<!-- Repository Name--->
# python-template

<!-- Short Repository Description--->
Generic template for my python projects in an effort to maintain common structure &amp; practices

<!-- Here is where you put generic information --->
This can be used when creating a repository by selecting it next to "Start with a template".

For more info on templates, refer to the [docs](./docs/)

## Testing

This template includes a pytest test setup for easy testing of your Python code.

### Installation

Install test dependencies:
```bash
pip install -r requirements-dev.txt
```

### Running Tests

Run all tests:
```bash
pytest
```

Run with coverage report:
```bash
pytest --cov=src --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_some_module.py
```

Run with verbose output:
```bash
pytest -v
```