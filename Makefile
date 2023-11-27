# Base build requirements are not installed automatically.
# Inspired by https://meson-python.readthedocs.io/en/latest/how-to-guides/editable-installs.html
dev:
	$(info [INFO] Make sure you're using a virtual environment for development)
	python3 -m pip install meson-python meson ninja
	python3 -m pip install --no-build-isolation --config-settings=editable-verbose=true --config-settings=setup-args=-Dbuildtype=debug --editable .[test,typing,lint,docs]

install:
	pip3 install .

init-test:
	pip3 install .[test]

test:
	python3 -m pytest --durations=10 --cov=./ --cov-report term-missing:skip-covered tests/

check:
	mypy perun/

docs:
	$(MAKE) -C docs html

docs-latex:
	$(MAKE) -C docs latex

docs-all:
	$(MAKE) -C docs html
	$(MAKE) -C docs dirhtml
	$(MAKE) -C docs latex

docs-release: dev docs-latex docs
	cp ./docs/_build/latex/Perun.pdf ./docs/pdf/perun.pdf

pypi-release:
	python3 -m build

.PHONY: init test docs install dev run-gui gh-pages docs-latex docs-release docs-all

