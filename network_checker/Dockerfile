FROM phusion/baseimage
ENV ARCH amd64
ENV DIST trusty
RUN echo 'deb http://fuel-repository.mirantis.com/fwm/5.0/ubuntu trusty main' >> /etc/apt/sources.list
RUN apt-get -q update
RUN apt-get -y --force-yes install cliff-tablib python-pyparsing python-pypcap scapy python-pip wget openssh-server
RUN pip install pytest mock
RUN sudo locale-gen en_US.UTF-8

RUN mkdir -p /app
