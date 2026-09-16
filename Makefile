.PHONY: verify check test eval build

verify:
	bash scripts/verify-repo.sh

check: verify
	bash scripts/run-hook.sh check

test: verify
	bash scripts/run-hook.sh test

eval: verify
	bash scripts/run-hook.sh eval smoke

build: verify
	bash scripts/run-hook.sh build
