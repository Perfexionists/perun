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
	$(MAKE) -C docs dirhtml

.PHONY: init test docs install dev run-gui
