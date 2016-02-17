/*
 * Copyright 2016 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/

define([
  'intern!object',
  'tests/functional/pages/common',
  'tests/functional/pages/cluster',
  'tests/functional/nightly/library/networks'
], function(registerSuite, Common, ClusterPage, NetworksLib) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      clusterName,
      networksLib;

    return {
      name: 'Neutron VLAN segmentation',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        networksLib = new NetworksLib(this.remote);
        clusterName = common.pickRandomName('VLAN Cluster');

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(clusterName);
          })
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return common.addNodesToCluster(1, ['Compute']);
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          });
      },
      'Storage Network "IP Ranges" testing': function() {
        this.timeout = 45000;
        var networkName = 'Storage';
        var correctIpRange = ['192.168.1.5', '192.168.1.10'];
        var newIpRange = ['192.168.1.25', '192.168.1.30'];
        return this.remote
          .then(function() {
            return networksLib.checkNetworkInitialState(networkName);
          })
          .then(function() {
            return networksLib.checkNetrworkIpRanges(networkName, correctIpRange, newIpRange);
          });
      },
      'Management Network "IP Ranges" testing': function() {
        this.timeout = 45000;
        var networkName = 'Management';
        var correctIpRange = ['192.168.0.55', '192.168.0.100'];
        var newIpRange = ['192.168.0.120', '192.168.0.170'];
        return this.remote
          .then(function() {
            return networksLib.checkNetworkInitialState(networkName);
          })
          .then(function() {
            return networksLib.checkNetrworkIpRanges(networkName, correctIpRange, newIpRange);
          });
      },
      'Check intersections between all networks': function() {
        this.timeout = 45000;
        return this.remote
          // Storage and Management
          .then(function() {
            return networksLib.checkNerworksIntersection('Storage', 'Management',
              ['192.168.0.0/24', '192.168.0.1', '192.168.0.254']);
          })
          // Storage and Public
          .then(function() {
            return networksLib.checkNerworksIntersection('Storage', 'Public',
              ['172.16.0.0/24', '172.16.0.5', '172.16.0.120']);
          })
          // Storage and Floating IP
          .then(function() {
            return networksLib.checkNerworksIntersection('Storage', 'Public',
              ['172.16.0.0/24', '172.16.0.135', '172.16.0.170']);
          })
          // Management and Public
          .then(function() {
            return networksLib.checkNerworksIntersection('Management', 'Public',
              ['172.16.0.0/24', '172.16.0.5', '172.16.0.120']);
          })
          // Management and Floating IP
          .then(function() {
            return networksLib.checkNerworksIntersection('Management', 'Public',
              ['172.16.0.0/24', '172.16.0.135', '172.16.0.170']);
          });
      }
    };
  });

  registerSuite(function() {
    var common,
      clusterPage,
      clusterName,
      networksLib;

    return {
      name: 'Neutron tunneling segmentation',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        networksLib = new NetworksLib(this.remote);
        clusterName = common.pickRandomName('Tunneling Cluster');

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(
              clusterName,
              {
                'Networking Setup': function() {
                  return this.remote
                    .clickByCssSelector('input[value*="neutron"][value$=":vlan"]')
                    .clickByCssSelector('input[value*="neutron"][value$=":tun"]');
                }
              }
            );
          })
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .then(function() {
            return common.addNodesToCluster(1, ['Compute']);
          })
          .then(function() {
            return clusterPage.goToTab('Networks');
          });
      },
      'Storage Network "IP Ranges" testing': function() {
        this.timeout = 45000;
        var networkName = 'Storage';
        var correctIpRange = ['192.168.1.5', '192.168.1.10'];
        var newIpRange = ['192.168.1.25', '192.168.1.30'];
        return this.remote
          .then(function() {
            return networksLib.checkNetworkInitialState(networkName);
          })
          .then(function() {
            return networksLib.checkNetrworkIpRanges(networkName, correctIpRange, newIpRange);
          });
      },
      'Management Network "IP Ranges" testing': function() {
        this.timeout = 45000;
        var networkName = 'Management';
        var correctIpRange = ['192.168.0.55', '192.168.0.100'];
        var newIpRange = ['192.168.0.120', '192.168.0.170'];
        return this.remote
          .then(function() {
            return networksLib.checkNetworkInitialState(networkName);
          })
          .then(function() {
            return networksLib.checkNetrworkIpRanges(networkName, correctIpRange, newIpRange);
          });
      },
      'Private Network "IP Ranges" testing': function() {
        this.timeout = 45000;
        var networkName = 'Private';
        var correctIpRange = ['192.168.2.190', '192.168.2.200'];
        var newIpRange = ['192.168.2.200', '192.168.2.230'];
        return this.remote
          .then(function() {
            return networksLib.checkNetworkInitialState(networkName);
          })
          .then(function() {
            return networksLib.checkNetrworkIpRanges(networkName, correctIpRange, newIpRange);
          });
      },
      'Check intersections between all networks': function() {
        this.timeout = 60000;
        return this.remote
          // Storage and Management
          .then(function() {
            return networksLib.checkNerworksIntersection('Storage', 'Management',
              ['192.168.0.0/24', '192.168.0.1', '192.168.0.254']);
          })
          // Storage and Private
          .then(function() {
            return networksLib.checkNerworksIntersection('Storage', 'Private',
              ['192.168.2.0/24', '192.168.2.1', '192.168.2.254']);
          })
          // Storage and Public
          .then(function() {
            return networksLib.checkNerworksIntersection('Storage', 'Public',
              ['172.16.0.0/24', '172.16.0.5', '172.16.0.120']);
          })
          // Storage and Floating IP
          .then(function() {
            return networksLib.checkNerworksIntersection('Storage', 'Public',
              ['172.16.0.0/24', '172.16.0.135', '172.16.0.170']);
          })
          // Management and Public
          .then(function() {
            return networksLib.checkNerworksIntersection('Management', 'Public',
              ['172.16.0.0/24', '172.16.0.5', '172.16.0.120']);
          })
          // Management and Floating IP
          .then(function() {
            return networksLib.checkNerworksIntersection('Management', 'Public',
              ['172.16.0.0/24', '172.16.0.135', '172.16.0.170']);
          })
          // Private and Public
          .then(function() {
            return networksLib.checkNerworksIntersection('Private', 'Public',
              ['172.16.0.0/24', '172.16.0.5', '172.16.0.120']);
          })
          // Private and Floating IP
          .then(function() {
            return networksLib.checkNerworksIntersection('Private', 'Public',
              ['172.16.0.0/24', '172.16.0.135', '172.16.0.170']);
          });
      }
    };
  });
});
