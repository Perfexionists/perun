init:
	pip3 install -r requirements.txt

test:
	python3 -m pytest --cov=./

run-gui:
	python3 perun/view/gui/perun.py

dev:
	python3 setup.py develop

install:
	python3 setup.py install

docs:
	$(MAKE) -C docs html

docs-latex:
	$(MAKE) -C docs latex

docs-all:
	$(MAKE) -C docs html
	$(MAKE) -C docs dirhtml
	$(MAKE) -C docs latex

docs-release: docs-latex
	cp ./docs/_build/latex/Perun.pdf ./docs/pdf/perun.pdf

.PHONY: init test docs install dev run-gui
