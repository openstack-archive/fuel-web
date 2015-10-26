help:
	@echo "release - package and upload a release"

release:
	rm -rf dist build
	python setup.py sdist upload
	python setup.py bdist_wheel upload
