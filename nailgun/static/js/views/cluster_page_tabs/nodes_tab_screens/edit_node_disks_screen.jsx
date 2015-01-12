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
    'jsx!component_mixins',
    'jsx!views/dialogs',
    'jquery-autoNumeric'
],
function($, _, i18n, Backbone, React, utils, models, componentMixins, dialogs) {
    'use strict';

    var ScreenMixin = {
        goToNodeList: function() {
            app.navigate('#cluster/' + this.props.cluster.get('id') + '/nodes', {trigger: true});
        },
        isLockedScreen: function() {
            return this.props.cluster && !!this.props.cluster.tasks({group: 'deployment', status: 'running'}).length;
        },
        returnToNodeList: function() {
            if (this.hasChanges()) {
                dialogs.DiscardSettingsChangesDialog.show({cb: _.bind(this.goToNodeList, this)});
            } else {
                this.goToNodeList();
            }
        }
    };

    var EditNodeDisksScreen = React.createClass({
        mixins: [
            ScreenMixin,
            componentMixins.backboneMixin('disks')
        ],
        statics: {
            fetchData: function(options) {
                var cluster = options.cluster,
                    nodeIds = utils.deserializeTabOptions(options.screenOptions[0]).nodes.split(',').map(function(id) {return parseInt(id, 10);}),
                    nodes = new models.Nodes(cluster.get('nodes').getByIds(nodeIds));
                if (nodes.length) {
                    var volumes = new models.Volumes();
                    volumes.url = _.result(nodes.at(0), 'url') + '/volumes';
                    return $.when.apply($, nodes.map(function(node) {
                            node.disks = new models.Disks();
                            return node.disks.fetch({url: _.result(node, 'url') + '/disks'});
                        }, this).concat(volumes.fetch()))
                        .then(_.bind(function() {
                            var disks = new models.Disks(_.cloneDeep(nodes.at(0).disks.toJSON()), {parse: true});
                            return {
                                nodes: nodes,
                                disks: disks,
                                volumes: volumes
                            };
                        }, this));
                } else ScreenMixin.goToNodeList();
            }
        },
        getInitialState: function() {
            return {
                actionInProgress: false,
                resetData: false
            };
        },
        hasChanges: function() {
            var volumes = _.pluck(this.props.disks.toJSON(), 'volumes');
            return !this.props.nodes.reduce(function(result, node) {
                return result && _.isEqual(volumes, _.pluck(node.disks.toJSON(), 'volumes'));
            }, true);
        },
        hasValidationErrors: function() {
            var result = false;
            this.props.disks.each(function(disk) {result = result || disk.validationError || _.some(disk.get('volumes').models, 'validationError');}, this);
            return result;
        },
        isLocked: function() {
            var hasLockedNodes = this.props.nodes.any(function(node) {
                return !node.get('pending_addition') || _.contains(['ready', 'error'], node.get('status'));
            });
            return hasLockedNodes || this.isLockedScreen();
        },
        loadDefaults: function() {
            this.setState({actionInProgress: true});
            this.props.disks.fetch({url: _.result(this.props.nodes.at(0), 'url') + '/disks/defaults/'})
                .fail(_.bind(function(response) {
                    utils.showErrorDialog({
                        title: i18n('cluster_page.nodes_tab.configure_disks.configuration_error.title'),
                        message: utils.getResponseText(response) || i18n('cluster_page.nodes_tab.configure_disks.configuration_error.load_defaults_warning')
                    });
                }, this))
                .always(_.bind(function() {
                    this.setState({
                        actionInProgress: false,
                        resetData: true
                    });
                }, this));
        },
        revertChanges: function() {
            this.props.disks.reset(_.cloneDeep(this.props.nodes.at(0).disks.toJSON()), {parse: true});
            this.setState({resetData: true});
        },
        applyChanges: function() {
            var cluster = this.props.cluster;
            return $.when.apply($, this.props.nodes.map(function(node) {
                    node.disks.each(function(disk, index) {
                        disk.set({volumes: new models.Volumes(this.props.disks.at(index).get('volumes').toJSON())});
                    }, this);
                    return Backbone.sync('update', node.disks, {url: _.result(node, 'url') + '/disks'});
                }, this))
                .done(_.bind(function() {
                    cluster.fetch();
                    this.setState({resetData: true});
                }, this))
                .fail(_.bind(function(response) {
                    utils.showErrorDialog({
                        title: i18n('cluster_page.nodes_tab.configure_disks.configuration_error.title'),
                        message: utils.getResponseText(response) || i18n('cluster_page.nodes_tab.configure_disks.configuration_error.saving_warning')
                    });
                }, this));
        },
        mapVolumesColors: function() {
            var volumesColors = {},
                colors = ['#23a85e', '#2b6ba9', '#c38812', '#189f99', '#870a0d', '#7a44ac', '#1b88c1', '#71a623', '#6b3e00'];
            this.props.volumes.each(function(volume, index) {
                volumesColors[volume.get('name')] = colors[index];
            }, this);
            volumesColors.unallocated = '#999';
            return volumesColors;
        },
        getDiskMetaData: function(disk) {
            var result,
                disksMetaData = this.props.nodes.at(0).get('meta').disks;
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
        refresh: function() {
            this.setState({resetData: false});
        },
        render: function() {
            var locked = this.isLocked(),
                hasChanges = this.hasChanges(),
                hasErrors = this.hasValidationErrors(),
                loadDefaultsEnabled = !this.state.actionInProgress && !locked,
                revertChangesEnabled = !this.state.actionInProgress && hasChanges,
                applyEnabled = !hasErrors && !this.state.actionInProgress && hasChanges;
            return (
                <div className='edit-node-disks-screen'>
                    <div className='row'>
                        <div className='title'>
                            {i18n('cluster_page.nodes_tab.configure_disks.title', {count: this.props.nodes.length, name: this.props.nodes.length && this.props.nodes.at(0).get('name')})}
                        </div>
                        <div className='col-xs-12 node-disks'>
                            {this.state.actionInProgress &&
                                <div className='progress'>
                                    <div className='progress-bar progress-bar-striped active' style={{width: '100%'}}></div>
                                </div>
                            }
                            {_.map(this.props.disks.models, function(disk, index) {
                                return (<NodeDisk
                                    disk={disk}
                                    key={index}
                                    refresh={this.refresh}
                                    resetData={this.state.resetData}
                                    disabled={this.state.actionInProgress}
                                    volumes={this.props.volumes.models}
                                    diskMetaData={this.getDiskMetaData(disk)}
                                    volumesColors={this.mapVolumesColors()}
                                />);
                            }, this)}
                        </div>
                        <div className='col-xs-12 page-buttons'>
                            <div className='well clearfix'>
                                <div className='btn-group'>
                                    <button onClick={this.returnToNodeList} className='btn btn-default btn-return'>{i18n('cluster_page.nodes_tab.back_to_nodes_button')}</button>
                                </div>
                                <div className='btn-group pull-right'>
                                    <button className='btn btn-default btn-defaults' onClick={this.loadDefaults} disabled={!loadDefaultsEnabled}>{i18n('common.load_defaults_button')}</button>
                                    <button className='btn btn-default btn-revert-changes' onClick={this.revertChanges} disabled={!revertChangesEnabled}>{i18n('common.cancel_changes_button')}</button>
                                    <button className='btn btn-success btn-apply' onClick={this.applyChanges} disabled={!applyEnabled}>{i18n('common.apply_button')}</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    var NodeDisk = React.createClass({
        mixins: [
            componentMixins.backboneMixin('disk', 'chage invalid')
        ],
        loadInitialState: function(disk) {
            this.setState({
                volumesInfo: this.getVolumesInfo(null, disk),
                visible: false
            });
        },
        componentWillMount: function() {
            this.loadInitialState(this.props.disk);
        },
        componentWillReceiveProps: function(nextProps) {
            if (nextProps.resetData) this.loadInitialState(nextProps.disk);
        },
        componentDidMount: function() {
            $('.disk-details', this.getDOMNode())
                .on('show.bs.collapse', _.bind(function() {this.setState({visible: true})}, this))
                .on('hide.bs.collapse', _.bind(function() {this.setState({visible: false})}, this));
        },
        getVolumesInfo: function(e, disk) {
            if (!disk) disk = this.props.disk;
            var volumes = this.state ? this.state.volumesInfo : {},
                unallocatedWidth = 100,
                unallocatedSize = disk.get('size');
            _.each(disk.get('volumes').models, function(volume, index) {
                var size = volume.get('size') || 0,
                    width = this.getVolumeWidth(size),
                    inputSize = size;
                if (e && e.target.name == volume.get('name')) inputSize = parseInt(e.target.value);
                unallocatedWidth -= width;
                unallocatedSize -= size;
                volumes[volume.get('name')] = {
                    inputSize: inputSize,
                    size: size,
                    width: width,
                    showRemoveButton: volume.getMinimalSize(this.props.volumes[index].get('min_size')) <= 0
                };
            }, this);
            volumes.unallocated = {
                size: unallocatedSize,
                width: unallocatedWidth
            };
            return volumes;
        },
        getVolumeWidth: function(size) {
            return this.props.disk.get('size') ? utils.floor(size / this.props.disk.get('size') * 100, 2) : 0;
        },
        updateDisk: function(name, value, e) {
            var disk = this.props.disk;
            disk.get('volumes').each(function(volume, index) {
                if (name == volume.get('name')) {
                    volume.set({size: parseInt(value)}, {validate: true, minimum: this.props.volumes[index].get('min_size'), maximum: volume});
                }
            }, this); // volumes validation (minimum)
            disk.set({volumes: disk.get('volumes')}, {validate: true}); // disk validation (maximum)
            this.setState({volumesInfo: this.getVolumesInfo(e)});
            this.props.refresh();
        },
        handleVolumeSize: function(e) {
            this.updateDisk(e.target.name, e.target.value, e);
        },
        useAllAllowedSpace: function(e) {
            var value = _.max([0, this.state.volumesInfo[e.target.name].size + this.state.volumesInfo.unallocated.size]);
            this.updateDisk(e.target.name, value);
        },
        deleteVolume: function(e) {
            var name = $(e.currentTarget).parents('.volume-group').data('volume');
            this.updateDisk(name, 0);
        },
        render: function() {
            var disk = this.props.disk,
                volumesInfo = this.state.volumesInfo,
                diskMetaData = this.props.diskMetaData,
                sortOrder = ['name', 'model', 'size'];
            return (
                <div className='col-xs-12 disk-box' data-disk={disk.id} key={this.props.key}>
                    <div className='row'>
                        <h4 className='col-xs-6'>
                            {disk.get('name')} ({disk.id})
                        </h4>
                        <h4 className='col-xs-6 text-right'>
                            {i18n('cluster_page.nodes_tab.configure_disks.total_space')} : {utils.showDiskSize(disk.get('size'), 2)}
                        </h4>
                    </div>
                    <div className='row disk-visual clearfix'>
                        {_.map(this.props.volumes, function(volume) {
                            var style = {
                                    width: volumesInfo[volume.get('name')].width + '%',
                                    background: this.props.volumesColors[volume.get('name')]
                                },
                                classes = {
                                    'close-btn': true,
                                    hide: !volumesInfo[volume.get('name')].showRemoveButton || !this.state.visible
                                };
                            return (
                                <div className={'volume-group pull-left ' + volume.get('name')} data-volume={volume.get('name')} key={'volume_' + volume.get('name')} style={style}>
                                    <div className='text-center' data-toggle='collapse' data-target={'#' + disk.get('name')}>
                                        <div>{volume.get('label')}</div>
                                        <div className='volume-group-size'>{utils.showDiskSize(volumesInfo[volume.get('name')].size, 2)}</div>
                                    </div>
                                    <div className={utils.classNames(classes)} onClick={this.deleteVolume} name={volume.get('name')}>&times;</div>
                                </div>
                            );
                        }, this)}
                        <div className='volume-group pull-left' ref={'volume_unallocated'} style={{width: volumesInfo.unallocated.width + '%', background: this.props.volumesColors.unallocated}}>
                            <div className='text-center' data-toggle='collapse' data-target={'#' + disk.get('name')}>
                                <div className='volume-group-name'>{i18n('cluster_page.nodes_tab.configure_disks.unallocated')}</div>
                                <div className='volume-group-size'>{utils.showDiskSize(volumesInfo.unallocated.size, 2)}</div>
                            </div>
                        </div>
                    </div>
                    <div className='row collapse disk-details' id={disk.get('name')} key='diskDetails' ref={disk.get('name')}>
                        <div className='col-xs-6'>
                            {diskMetaData &&
                                <div>
                                <h5>{i18n('cluster_page.nodes_tab.configure_disks.disk_information')}</h5>
                                <div className='form-horizontal disk-info-box'>
                                    {_.map(utils.sortEntryProperties(diskMetaData, sortOrder), function(propertyName) {
                                        return (
                                            <div className='form-group' key={'property_' + propertyName}>
                                                <label className='col-xs-2'>{propertyName.replace(/_/g, ' ')}</label>
                                                <div className='col-xs-10'>
                                                    <p className='form-control-static'>
                                                        {propertyName == 'size' ? utils.showDiskSize(diskMetaData[propertyName]) : diskMetaData[propertyName]}
                                                    </p>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                                </div>
                            }
                        </div>
                        <div className='col-xs-6'>
                            <h5>{i18n('cluster_page.nodes_tab.configure_disks.volume_groups')}</h5>
                            <div className='form-horizontal disk-utility-box'>
                                {_.map(this.props.volumes, function(volume) {
                                    var volumeName = volume.get('name'),
                                        diskInfo = disk.get('volumes').findWhere({name: volume.get('name')}),
                                        inputClasses = {
                                            'has-error': !!diskInfo.validationError,
                                            'col-xs-4': true,
                                            'volume-group-input': true
                                        };
                                    return (
                                        <div key={'edit_' + volumeName}>
                                            <div className='form-group volume-group row' data-volume={volumeName}>
                                                <label className='col-xs-3'>
                                                    <span ref={'volume-group-flag ' + volumeName} style={{background: this.props.volumesColors[volume.get('name')]}}> &nbsp; </span>
                                                    {volume.get('label')}
                                                </label>
                                                <div className='col-xs-4 volume-group-use-all-allowed-btn'>
                                                    {!this.props.disabled &&
                                                        <button className='btn-link' name={volumeName} onClick={this.useAllAllowedSpace}>
                                                            {i18n('cluster_page.nodes_tab.configure_disks.use_all_allowed_space')}
                                                        </button>
                                                    }
                                                </div>
                                                <div className={utils.classNames(inputClasses)}>
                                                    <input
                                                        type='range'
                                                        onChange={this.handleVolumeSize}
                                                        name={volumeName}
                                                        min='0'
                                                        max={disk.get('size')}
                                                        key={'range_' + volumeName}
                                                        value={volumesInfo[volume.get('name')].size || 0}
                                                        disabled={this.props.disabled}/>
                                                    <input
                                                        id={disk.id + '-' + volume.get('name')}
                                                        onChange={this.handleVolumeSize}
                                                        type='number'
                                                        min='0'
                                                        max={disk.get('size')}
                                                        key={'input_' + volumeName}
                                                        className='form-control'
                                                        name={volumeName}
                                                        value={volumesInfo[volume.get('name')].inputSize || 0}
                                                        disabled={this.props.disabled}/>
                                                </div>
                                                <div className='col-xs-1 volume-group-size-label'>{i18n('common.size.mb')}</div>
                                            </div>
                                            {diskInfo.validationError &&
                                                <div className='col-xs-12 volume-group-error text-right'>{diskInfo.validationError}</div>
                                            }
                                        </div>
                                    );
                                }, this)}
                                <div className='volume-group-error common text-red text-right'></div>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return EditNodeDisksScreen;
});
