FROM ubuntu:22.04
USER root
COPY . /usr/app/
RUN chmod -R 777 /usr/app/
WORKDIR /usr/app/
RUN ls ./streamlit-app/
RUN apt-get update && apt-get install -y python3 python3-pip && pip install --upgrade pip && pip install -r requirements.txt
RUN apt-get install -y lsb-release curl && apt-get clean all
RUN apt-get install -y ffmpeg
RUN chmod +x ./odbc.sh
RUN ./odbc.sh
COPY run.sh run.sh
USER root
RUN chmod a+x run.sh
CMD ["./run.sh"]