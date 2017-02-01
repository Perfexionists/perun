init:
	pip3 install -r requirements.txt

test:
	py.test test

run-gui:
	python3 perun/view/gui/perun.py

install:
	python3 setup.py install

.PHONY: init test
