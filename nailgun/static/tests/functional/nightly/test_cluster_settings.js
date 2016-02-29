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
  'tests/functional/nightly/library/settings'
], function(registerSuite, Common, ClusterPage, SettingsLib) {
  'use strict';

  registerSuite(function() {
    var common,
      clusterPage,
      clusterName,
      settingsLib;

    return {
      name: 'Settings Tab Segment',
      setup: function() {
        common = new Common(this.remote);
        clusterPage = new ClusterPage(this.remote);
        settingsLib = new SettingsLib(this.remote);
        clusterName = common.pickRandomName('VLAN Cluster');

        return this.remote
          .then(function() {
            return common.getIn();
          })
          .then(function() {
            return common.createCluster(clusterName);
          })
          .then(function() {
            return clusterPage.goToTab('Settings');
          });
      },
      'Check "General" segment': function() {
        var pageTitleSelector = 'div.title';
        var segmentSelector = 'li.active a.subtab-link-general';
        return this.remote
          .assertElementMatchesRegExp(pageTitleSelector, /OpenStack Settings/i,
            'OpenStack Settings page has default name')
          .assertElementsExist(segmentSelector, 'General Settings segment link exists and active')
          .assertElementMatchesRegExp(segmentSelector, /General/i,
            'General Settings segment link name is correct')
          .then(function() {
            return settingsLib.checkGeneralSegment();
          })
          .assertElementEnabled('button.btn-load-defaults', '"Load Defaults" button is enabled')
          .assertElementDisabled('button.btn-revert-changes', '"Cancel Changes" button is disabled')
          .assertElementDisabled('button.btn-apply-changes', '"Save Settings" button is disabled');
      },
      'Check "Security" segment': function() {
        var segmentName = 'Security';
        return this.remote
          .then(function() {
            return settingsLib.gotoOpenStackSettings(segmentName);
          })
          .then(function() {
            return settingsLib.checkSecuritySegment();
          });
      },
      'Check "Compute" segment': function() {
        var segmentName = 'Compute';
        return this.remote
          .then(function() {
            return settingsLib.gotoOpenStackSettings(segmentName);
          })
          .then(function() {
            return settingsLib.checkComputeSegment();
          });
      },
      'Check "Storage" segment': function() {
        var segmentName = 'Storage';
        return this.remote
          .then(function() {
            return settingsLib.gotoOpenStackSettings(segmentName);
          })
          .then(function() {
            return settingsLib.checkStorageSegment();
          });
      },
      'Check "Logging" segment': function() {
        var segmentName = 'Logging';
        return this.remote
          .then(function() {
            return settingsLib.gotoOpenStackSettings(segmentName);
          })
          .then(function() {
            return settingsLib.checkLoggingSegment();
          });
      },
      'Check "OpenStack Services" segment': function() {
        var segmentName = 'OpenStack Services';
        return this.remote
          .then(function() {
            return settingsLib.gotoOpenStackSettings(segmentName);
          })
          .then(function() {
            return settingsLib.checkOpenStackServicesSegment();
          });
      },
      'Check "Other" segment': function() {
        var segmentName = 'Other';
        return this.remote
          .then(function() {
            return settingsLib.gotoOpenStackSettings(segmentName);
          })
          .then(function() {
            return settingsLib.checkOtherSegment();
          });
      },
      'User returns to the selected segment on "Settings" tab': function() {
        return this.remote
          .then(function() {
            return clusterPage.goToTab('Nodes');
          })
          .assertElementsAppear('a.nodes.active', 2000, '"Nodes" tab is opened')
          .then(function() {
            return clusterPage.goToTab('Settings');
          })
          .assertElementsAppear('a.settings.active', 2000, '"Settings" tab is opened')
          .assertElementsExist('div.other', '"Other" settings segment page is opened')
          .assertElementsExist('li.active a.subtab-link-other',
            '"Other" settings segment link exists and active')
          .assertElementMatchesRegExp('li.active a.subtab-link-other', /Other/i,
            '"Other" settings segment link name is correct')
          .then(function() {
            return settingsLib.checkOtherSegment();
          });
      },
      'No "Node network group" item via sorting/filtering for unallocated nodes': function() {
        var itemName = 'Node network group';
        var itemRegExp = RegExp('[\\s\\S]*[^(' + itemName + ')][\\s\\S]*', 'i');
        var btnSortSelector = 'button.btn-sorters:enabled';
        var btnFilterSelector = 'button.btn-filters:enabled';
        var btnMoreSelector = 'div.more-control button.btn-link';
        var popoverSelector = 'div.popover ';
        var popContentSelector = popoverSelector + 'div.popover-content div';
        return this.remote
          .then(function() {
            return clusterPage.goToTab('Nodes');
          })
          .assertElementsAppear('a.nodes.active', 2000, '"Nodes" tab is opened')
          .assertElementsExist('button.btn-add-nodes', '"Add Nodes" button exists')
          .clickByCssSelector('button.btn-add-nodes')
          // Check sorting
          .assertElementsAppear(btnSortSelector, 1000, '"Sort Nodes" button is exists')
          .clickByCssSelector(btnSortSelector)
          .assertElementsAppear('div.sorters', 1000, '"Sort" pane is appears')
          .assertElementsExist(btnMoreSelector, '"More" sort button exists')
          .clickByCssSelector(btnMoreSelector)
          .assertElementsAppear(popoverSelector, 1000, '"More" sort popover is appears')
          .assertElementNotExists('input[label="' + itemName + '"]', 'No "' + itemName +
            '" item checkbox via sorting for unallocated nodes')
          .assertElementMatchesRegExp(popContentSelector, itemRegExp, 'No "' + itemName +
            '" item label via sorting for unallocated nodes')
          // Check filtering
          .assertElementsAppear(btnFilterSelector, 1000, '"Filter Nodes" button is exists')
          .clickByCssSelector(btnFilterSelector)
          .assertElementsAppear('div.filters', 1000, '"Filter" pane is appears')
          .assertElementsExist(btnMoreSelector, '"More" filter button exists')
          .clickByCssSelector(btnMoreSelector)
          .assertElementsAppear(popoverSelector, 1000, '"More" filter popover is appears')
          .assertElementNotExists('input[label="' + itemName + '"]', 'No "' + itemName +
            '" item checkbox via filtering for unallocated nodes')
          .assertElementMatchesRegExp(popContentSelector, itemRegExp, 'No "' + itemName +
            '" item label via filtering for unallocated nodes');
      },
      'Check node roles edition': function() {
        var nodeSelector = 'div.node ';
        var btnEditSelector = 'button.btn-edit-roles';
        var btnApplySelector = 'button.btn-apply';
        var rolesRegExp = RegExp('[\\s\\S]*(controller.*|base-os.*){2}[\\s\\S]*', 'i');
        return this.remote
          .then(function() {
            return common.addNodesToCluster(1, ['Controller']);
          })
          .assertElementsExist(nodeSelector + 'input', '"Controller" node exists')
          .clickByCssSelector(nodeSelector + 'input')
          .assertElementsExist(btnEditSelector, '"Edit Roles" button exists')
          .clickByCssSelector(btnEditSelector)
          .then(function() {
            return clusterPage.checkNodeRoles(['Operating System']);
          })
          .assertElementsExist(btnApplySelector, '"Apply Changes" button exists')
          .clickByCssSelector(btnApplySelector)
          .waitForElementDeletion(btnApplySelector, 2000)
          .assertElementMatchesRegExp(nodeSelector + 'div.role-list', rolesRegExp,
            '"Controller" and "Operating System" node roles are observed');
      }
    };
  });
});
