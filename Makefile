local-server:
	./local_server.sh

deploy:
	@if [ `whoami` == 'ci' ]; then \
		./update_and_restart.sh; \
	else \
		cat update_and_restart.sh | ssh ka-ci sh; \
	fi

clean:
	rm *.pyc
	rm dump.rdb

.PHONY: local-server clean
