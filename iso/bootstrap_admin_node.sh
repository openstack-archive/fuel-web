#!/bin/bash

function countdown() {
  local i 
  printf %s "$1"
  sleep 1
  for ((i=$1-1; i>=1; i--)); do
    printf '\b%d' "$i"
    sleep 1
  done
}

showmenu="no"
if [ -f /root/.showfuelmenu ]; then
  . /root/.showfuelmenu
fi
if [[ "$showmenu" == "yes" || "$showmenu" == "YES" ]]; then
  fuelmenu
  else
  #Give user 5 seconds to enter fuelmenu or else continue
  echo
  echo -n "Press any key to enter Fuel Setup... "
  countdown 5 & pid=$!
  if ! read -s -n 1 -t 5; then
    echo
    echo -e "\nSkipping Fuel Setup..."
  else
    kill "$pid"
    echo -e "\nEntering Fuel Setup..."
    fuelmenu
  fi
fi
#Reread /etc/sysconfig/network to inform puppet of changes
. /etc/sysconfig/network
hostname "$HOSTNAME"
#Update motd for IP
primary="$(grep mnbs_internal_interface= /etc/naily.facts | cut -d'=' -f2) "
echo "sed -i \"s%\(^.*able on:\).*$%\1 http://\`ip address show $primary | awk '/inet / {print \$2}' | cut -d/ -f1 -\`:8000%\" /etc/issue" >>/etc/rc.local 
sed -i "s%\(^.*able on:\).*$%\1 http://`ip address show $primary | awk '/inet / {print \$2}' | cut -d/ -f1 -`:8000%" /etc/issue

puppet apply  /etc/puppet/modules/nailgun/examples/site.pp
