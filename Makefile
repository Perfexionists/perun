# Setuptools fails for nested requirements file when installed as `pip install .`, so sadly no
# simple "dev" optional dependency
dev:
	pip3 install -e .[typing,lint,test,docs]

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

