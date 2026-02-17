# set base image (host OS)
FROM python:3.7-slim
# set the working directory in the container
WORKDIR /code

# copy the dependencies file to the working directory
COPY requirements.txt .

# install dependencies
RUN pip install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY configurations/ .
COPY ../run_algorithm.py .
COPY genetic_island_algorithm.py .
# command to run on container start
CMD [ "python", "run_algorithm.py" ]