local-server:
	./local_server.sh

clean:
	rm *.pyc
	rm dump.rdb

.PHONY: local-server clean
