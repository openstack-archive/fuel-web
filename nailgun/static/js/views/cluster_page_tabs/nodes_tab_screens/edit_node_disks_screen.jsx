/*
 * Copyright 2013 Mirantis, Inc.
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
define(
[
    'jquery',
    'underscore',
    'i18n',
    'backbone',
    'react',
    'utils',
    'models',
    'jquery-autoNumeric'
],
function($, _, i18n, Backbone, React, utils, models) {
    'use strict';

    var cx = React.addons.classSet;

    var ScreenMixin = {
        goToNodeList: function() {
            app.navigate('#cluster/' + this.props.model.get('id') + '/nodes', {trigger: true});
        },
        isLockedScreen: function() {
            return this.model && !!this.model.tasks({group: 'deployment', status: 'running'}).length;
        },
        returnToNodeList: function() {
            if (this.hasChanges()) {
                app.page.discardSettingsChanges({cb: _.bind(this.goToNodeList, this)});
            } else {
                this.goToNodeList();
            }
        }
    };

    var EditNodeDisksScreen = React.createClass({
        mixins: [
            ScreenMixin
        ],
        getInitialState: function() {
            return {
                disks: []
            };
        },
        componentWillMount: function() {
            var cluster = this.props.model,
                nodeIds = utils.deserializeTabOptions(this.props.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);});
                this.nodes = new models.Nodes(cluster.get('nodes').getByIds(nodeIds));
            console.log(this.props.volumes);
            if (this.nodes.length) {
                this.volumes = new models.Volumes();
                this.volumes.url = _.result(this.nodes.at(0), 'url') + '/volumes';
                this.loading = $.when.apply($, this.nodes.map(function(node) {
                        node.disks = new models.Disks();
                        return node.disks.fetch({url: _.result(node, 'url') + '/disks'});
                    }, this).concat(this.volumes.fetch()))
                    .done(_.bind(function() {
                        this.disks = new models.Disks(_.cloneDeep(this.nodes.at(0).disks.toJSON()), {parse: true});
                        this.setState({
                            disks: this.disks
                        });
                        this.mapVolumesColors();
                    }, this))
                    .fail(_.bind(this.goToNodeList, this));
            } else {
                this.goToNodeList();
            }
        },
        hasChanges: function() {
            //var volumes = _.pluck(this.disks.toJSON(), 'volumes');
            //return !this.nodes.reduce(function(result, node) {
            //    return result && _.isEqual(volumes, _.pluck(node.disks.toJSON(), 'volumes'));
            //}, true);
        },
        hasValidationErrors: function() {
            var result = false;
            this.disks.each(function(disk) {result = result || disk.validationError || _.some(disk.get('volumes').models, 'validationError');}, this);
            return result;
        },
        isLocked: function() {
            var nodesAvailableForChanges = this.nodes.filter(function(node) {
                return node.get('pending_addition') || (node.get('status') == 'error' && node.get('error_type') == 'provision');
            });
            return !nodesAvailableForChanges.length || this.constructor.__super__.isLocked.apply(this);
        },
        checkForChanges: function() {
            this.updateButtonsState(this.isLocked());
            this.applyChangesButton.set('disabled', this.isLocked() || !this.hasChanges() || this.hasValidationErrors());
            this.cancelChangesButton.set('disabled', this.isLocked() || (!this.hasChanges() && !this.hasValidationErrors()));
        },
        loadDefaults: function() {
            this.disableControls(true);
            this.disks.fetch({url: _.result(this.nodes.at(0), 'url') + '/disks/defaults/'})
                .fail(_.bind(function() {
                    utils.showErrorDialog({
                        title: i18n('cluster_page.nodes_tab.configure_disks.configuration_error.title'),
                        message: i18n('cluster_page.nodes_tab.configure_disks.configuration_error.load_defaults_warning')
                    });
                }, this));
        },
        revertChanges: function() {
            this.disks.reset(_.cloneDeep(this.nodes.at(0).disks.toJSON()), {parse: true});
        },
        applyChanges: function() {
            if (this.hasValidationErrors()) {
                return (new $.Deferred()).reject();
            }
            this.disableControls(true);
            return $.when.apply($, this.nodes.map(function(node) {
                    node.disks.each(function(disk, index) {
                        disk.set({volumes: new models.Volumes(this.disks.at(index).get('volumes').toJSON())});
                    }, this);
                    return Backbone.sync('update', node.disks, {url: _.result(node, 'url') + '/disks'});
                }, this))
                .done(_.bind(function() {
                    this.model.fetch();
                    this.render();
                }, this))
                .fail(_.bind(function(response) {
                    this.checkForChanges();
                    utils.showErrorDialog({
                        title: i18n('cluster_page.nodes_tab.configure_disks.configuration_error.title'),
                        message: utils.getResponseText(response) || i18n('cluster_page.nodes_tab.configure_disks.configuration_error.saving_warning')
                    });
                }, this));
        },
        mapVolumesColors: function() {
            this.volumesColors = {};
            var colors = [
                ['#23a85e', '#1d8a4d'],
                ['#3582ce', '#2b6ba9'],
                ['#eea616', '#c38812'],
                ['#1cbbb4', '#189f99'],
                ['#9e0b0f', '#870a0d'],
                ['#8f50ca', '#7a44ac'],
                ['#1fa0e3', '#1b88c1'],
                ['#85c329', '#71a623'],
                ['#7d4900', '#6b3e00']
            ];
            this.volumes.each(function(volume, index) {
                this.volumesColors[volume.get('name')] = colors[index];
            }, this);
        },
        getDiskMetaData: function(disk) {
            var result;
            var disksMetaData = this.nodes.at(0).get('meta').disks;
            // try to find disk metadata by matching "extra" field
            // if at least one entry presents both in disk and metadata entry,
            // this metadata entry is for our disk
            var extra = disk.get('extra') || [];
            result = _.find(disksMetaData, function(diskMetaData) {
                if (_.isArray(diskMetaData.extra)) {
                    return _.intersection(diskMetaData.extra, extra).length;
                }
                return false;
            }, this);

            // if matching "extra" fields doesn't work, try to search by disk id
            if (!result) {
                result = _.find(disksMetaData, {disk: disk.id});
            }

            return result;
        },
        render: function() {
            var nodes = this.nodes,
                disks = this.disks;
            return (
                <div className='edit-node-disks'>
                    <h3>
                        {i18n('cluster_page.nodes_tab.configure_disks.title', {count: nodes.length, name: nodes.length && nodes.at(0).get('name')})}
                    </h3>

                    <div className="node-disks">
                    </div>

                    <div className="row">
                        <div className="page-control-box">
                            <div className="back-button pull-left">
                                <button onClick={this.returnToNodeList} className="btn btn-return">{i18n('cluster_page.nodes_tab.back_to_nodes_button')}</button>
                            </div>
                            <div className="page-control-button-placeholder">
                                <button onClick={this.loadDefaults} className="btn btn-defaults">{i18n('common.load_defaults_button')}</button>
                                <button onClick={this.revertChanges} className="btn btn-revert-changes">{i18n('common.cancel_changes_button')}</button>
                                <button onClick={this.applyChanges} className="btn btn-success btn-apply">{i18n('common.apply_button')}</button>
                            </div>
                        </div>
                    </div>

                    {disks && _.map(disks.models, function(disk) {
                        return (<NodeDisk
                            disk={disk}
                            volumes={this.volumes}
                            diskMetaData={this.getDiskMetaData(disk)}
                            disabled={this.props.disabled}
                        />);
                    }, this)}
                </div>
                );
        }
    });

    var NodeDisk = React.createClass({
        componentWillMount: function() {
            
        },
        render: function() {
            var disk = this.props.disk,
                volumes = this.props.volumes,
                diskMetaData = this.props.diskMetaData,
                locked = this.props.disabled,
                sortOrder = ['name', 'model', 'size'];
            console.log('NodeDisk', volumes);
            return (
                <div className="disk-box disk" data-disk={disk.id}>

                    <div className="disk-box-name pull-left">{disk.get('name')} ({disk.id})</div>
                    <div className="disk-box-size pull-right">{i18n('cluster_page.nodes_tab.configure_disks.total_space')} : {utils.showDiskSize(disk.get('size'), 2)}</div>

                    <div className="disk-map-short disk-map-full">
                        <div className="disk-map-image disk-visual">
                            {volumes &&_.map(volumes.models, function(volume) {
                                return (
                                    <div className={'volume-group ' + volume.get('name')} data-volume={volume.get('name')} >
                                        <div className="toggle-volume">
                                            <div className="volume-group-name">{volume.get('label')}</div>
                                            <div className="volume-group-size">{utils.showDiskSize(0)}</div>
                                        </div>
                                        <div className="close-btn hide"></div>
                                    </div>
                                );
                            })}
                            <div className="volume-group unallocated">
                                <div className="toggle-volume">
                                    <div className="volume-group-name">{i18n('cluster_page.nodes_tab.configure_disks.unallocated')}</div>
                                    <div className="volume-group-size">{utils.showDiskSize(disk.get('size'), 2)}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="disk-map-details disk-form collapse">
                        <div className="disk-info-box">
                            {diskMetaData &&
                                <div>
                                    <div className="disk-box-title">{i18n('cluster_page.nodes_tab.configure_disks.disk_information')}</div>
                                    {_.map(utils.sortEntryProperties(diskMetaData, sortOrder), function(propertyName) {
                                        return (
                                            <div className="disk-map-details-item enable-selection">
                                                <div className="disk-map-details-name">{propertyName.replace(/_/g, ' ')}</div>
                                                <div className="disk-map-details-parameter">{propertyName == 'size' ? utils.showDiskSize(diskMetaData[propertyName]) : diskMetaData[propertyName]}</div>
                                            </div>
                                        );
                                    })}
                                </div>
                            }
                        </div>

                        <div className="disk-utility-box">
                            <div className="disk-box-title">{i18n('cluster_page.nodes_tab.configure_disks.volume_groups')}</div>
                            {volumes &&_.map(volumes.models, function(volume) {
                                return (
                                    <div>
                                        <div className="volume-group-box volume-group" data-volume={volume.get('name')} >
                                            <div className={'volume-group-box-flag' + volume.get('name')}></div>
                                            <div className="volume-group-box-name">{volume.get('label')}</div>
                                            <div className="pull-right">
                                                {!locked &&
                                                    <div className="volume-group-box-edit"><span className="use-all-allowed" data-i18n="cluster_page.nodes_tab.configure_disks.use_all_allowed_space"></span></div>
                                                }
                                                <div className="volume-group-box-input">
                                                    <input id={disk.id + '-' + volume.get('name')} className="input-medium" type="text" name={volume.get('name')} value={disk.get('volumes').findWhere({name: volume.get('name')}).get('size') || 0 } />
                                                </div>
                                                <div className="volume-group-box-sizetype">{i18n('common.size.mb')}</div>
                                            </div>
                                        </div>
                                        <div className="volume-group-error-message enable-selection"></div>
                                    </div>
                                );
                            })}
                            <div className="volume-group-error-message common enable-selection"></div>
                        </div>
                        <div className="clearfix"></div>
                    </div>
                  

                </div>

            );
        }
    });

    return EditNodeDisksScreen;
});
