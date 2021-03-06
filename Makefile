PACKNAME = catsim
all: install clean tests
clean:
	git clean -Xdf
install:
	pip install .
tests:
	pip install .[testing]

ifneq '$USER' 'travis'
	nosetests -s --cov-config .coveragerc --with-coverage --cover-package=catsim --processes=$(nproc)
else
	nosetests -s --cov-config .coveragerc --with-coverage --cover-package=catsim
endif
upload-test:
	python setup.py register -r pypitest && python setup.py sdist upload -r pypitest
upload:
	python setup.py register -r pypi && python setup.py sdist upload -r pypi
format: clean
	-yapf -i -r .
