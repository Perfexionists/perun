init:
	pip install -r requirements.txt

test:
	py.test test

run-gui:
	python perun/view/gui/perun.py

install:
	python setup.py install

.PHONY: init test
