init:
	pip install -r requirements.txt

test:
	py.test test

run-gui:
	python perun/view/gui/perun.py

.PHONY: init test
