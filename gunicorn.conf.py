# gunicorn.conf.py
workers = 1
threads = 2
worker_class = 'gthread'
worker_tmp_dir = '/dev/shm'
timeout = 120
bind = "0.0.0.0:10000"