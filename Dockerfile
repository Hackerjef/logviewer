FROM library/python:3.8.10
RUN apt update && apt install -y pipenv
COPY . /logviewer
WORKDIR /logviewer
RUN pipenv install
EXPOSE 8000
CMD ["pipenv", "run", "python3", "app.py"]
