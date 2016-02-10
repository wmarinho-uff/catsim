PACKNAME = catsim
all: install clean tests
clean:
	rm -rf $(PACKNAME).egg-info dist build
	find -name *.pyc -delete
	find -name __pycache__ -delete
install:
	sudo python3 setup.py install
tests:
	nosetests
upload-test:
	python setup.py register -r pypitest && python setup.py sdist upload -r pypitest
upload:
	python setup.py register -r pypi && python setup.py sdist upload -r pypi
format: clean
	-yapf -i -r .
