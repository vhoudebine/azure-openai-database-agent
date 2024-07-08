FROM ubuntu:22.04
USER root
COPY . /usr/app/
RUN chmod -R 777 /usr/app/
WORKDIR /usr/app/
RUN ls ./streamlit-app/
RUN apt-get update && apt-get install -y python3 python3-pip && pip install --upgrade pip && pip install -r requirements.txt
RUN apt-get install -y lsb-release curl && apt-get clean all
RUN chmod +x ./odbc.sh
RUN ./odbc.sh
#RUN chmod +x ./streamlit-app/app.py
ENTRYPOINT [ "python3" ]
CMD [ "-m", "streamlit", "run", "./streamlit-app/app.py" ]