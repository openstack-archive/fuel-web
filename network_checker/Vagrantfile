# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  config.vm.box = "precise64"

  config.vm.provider "virtualbox" do |v|
    v.customize ["modifyvm", :id, "--memory", 348]
  end

  config.vm.define :develop do |config|
    config.vm.network :private_network, ip: '10.100.0.0', type: "dhcp"
    config.vm.network :private_network, ip: '10.200.0.0', type: 'dhcp'
    config.vm.provision :shell, :inline => "echo 'deb http://fuel-repository.mirantis.com/fwm/5.0/ubuntu trusty main' >> /etc/apt/sources.list"
    config.vm.provision :shell, :inline => "sudo apt-get update"
    config.vm.provision :shell, :inline => "sudo apt-get -y --force-yes install cliff-tablib python-pyparsing python-pypcap scapy python-pip vde2"
    config.vm.provision :shell, :inline => "sudo pip install pytest mock"
    config.vm.provision :shell, :inline => "cd /vagrant && sudo python setup.py develop"
  end

end
