FROM golemfactory/base:1.5

RUN apt update
RUN apt install -y python3-pip

COPY tutorial_app /golem/tutorial_app
RUN python3 -m pip install --no-cache-dir --upgrade pip
RUN python3 -m pip install --no-cache-dir -r /golem/tutorial_app/requirements.txt
RUN python3 -m pip install --no-cache-dir /golem/tutorial_app

RUN apt remove -y python3-pip
RUN apt clean

WORKDIR /golem/work

ENTRYPOINT ["python3", "-m", "tutorial_app.entrypoint"]
