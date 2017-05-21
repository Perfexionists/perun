init:
	pip3 install -r requirements.txt

test:
	pytest

run-gui:
	python3 perun/view/gui/perun.py

dev:
	python3 setup.py develop

install:
	python3 setup.py install

.PHONY: init test
