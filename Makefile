test:
	python3 -m pytest --cov=./ --cov-report term-missing:skip-covered tests/

# Setuptools fails for nested requirements file when installed as `pip install .`, so sadly no
# simple "dev" optional dependency
dev:
	pip3 install -e .[typing,lint,test,docs]

install:
	pip3 install .

docs:
	$(MAKE) -C docs html

docs-latex:
	$(MAKE) -C docs latex

docs-all:
	$(MAKE) -C docs html
	$(MAKE) -C docs dirhtml
	$(MAKE) -C docs latex

docs-release: docs-latex docs
	cp ./docs/_build/latex/Perun.pdf ./docs/pdf/perun.pdf

# Releases the latest documentation to the gh-pages
# Warn: This should only be executed in isolate clone of the Perun!
gh-pages:
	git checkout master
	git pull
	git checkout gh-pages
	rm -rf build _sources _static
	git checkout master docs figs examples Makefile CHANGELOG.rst
	git reset HEAD
	cp CHANGELOG.rst docs/changelog.rst
	make docs
	mv -fv docs/_build/html/* ./
	rm -rf docs examples figs CHANGELOG.rst
	git add -A
	git commit -m "Generated gh-pages for version `git describe --tags `git rev-list --tags --max-count=1``"

.PHONY: init test docs install dev run-gui gh-pages docs-latex docs-release docs-all
