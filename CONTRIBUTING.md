# Contributing

The following is a set of guidelines for contributing to rapidsms-smpp-gateway
on GitHub. Use your best judgement, and feel free to propose changes to this
document in a pull request.


#### Table of contents

* [Local development](#local-development)
* [Tests](#tests)
* [Install an editable version in another project](#install-an-editable-version-in-another-project)


## Local development

You will first need to clone the repository using git and place yourself in its
directory:

```shell
git clone git@github.com:caktus/rapidsms-smpp-gateway.git
cd rapidsms-smpp-gateway/
```

Now, you will need to install the required dependencies for
rapidsms-smpp-gateway and be sure that the current tests are passing on your
machine:

```shell
# install poetry
brew install pipx
pipx install poetry
# then install requirements within activated venv
poetry install
```

To make sure that you don't accidentally commit code that does not follow the
coding style, you can install a pre-commit hook that will check that everything
is in order:

```
pre-commit install
```


## Tests

```shell
pytest
```


## Install an editable version in another project

```shell
pip install -e ../rapidsms-smpp-gateway/
```
