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
                utils.showDialog(dialogs.DiscardSettingsChangesDialog, {cb: _.bind(this.goToNodeList, this)});
            } else {
                this.goToNodeList();
            }
        }
    };

    var EditNodeDisksScreen = React.createClass({
        mixins: [
            ScreenMixin
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
                disks: []
            };
        },
        componentWillMount: function() {
            this.setState({
                disks: this.props.disks,
                volumes: this.props.volumes.models
            });
        },
        hasChanges: function() {
            // TODO understand what I need here this.state.disks or this.props.disks
            var volumes = _.pluck(this.props.disks.toJSON(), 'volumes');
            return !this.props.nodes.reduce(function(result, node) {
                return result && _.isEqual(volumes, _.pluck(node.disks.toJSON(), 'volumes'));
            }, true);
        },
        hasValidationErrors: function() {
            var result = false;
            this.state.disks.each(function(disk) {result = result || disk.validationError || _.some(disk.get('volumes').models, 'validationError');}, this);
            return result;
        },
        isLocked: function() {
            var nodesAvailableForChanges = this.props.nodes.filter(function(node) {
                return node.get('pending_addition') || (node.get('status') == 'error' && node.get('error_type') == 'provision');
            });
            return !nodesAvailableForChanges.length || this.constructor.__super__.isLocked.apply(this);
        },
        loadDefaults: function() {
            this.setState({actionInProgress: true});
            console.log('loadDefaults');
            this.setState({
                disks: this.props.disks
            });
            // $.when.apply($, this.props.nodes.map(function(node) {
            //         node.disks = new models.Disks();
            //         return node.disks.fetch({url: _.result(node, 'url') + '/disks/defaults/'});
            //     }, this).concat(this.props.volumes.fetch()))
            //     .done(_.bind(function() {
            //         console.log('loadDefaults');
            //         this.setState({
            //             actionInProgress: false,
            //             volumes: this.props.volumes.models
            //         })
            //     }, this))
            //     .fail(_.bind(function() {
            //         utils.showErrorDialog({
            //             title: i18n('cluster_page.nodes_tab.configure_disks.configuration_error.title'),
            //             message: i18n('cluster_page.nodes_tab.configure_disks.configuration_error.load_defaults_warning')
            //         });
            //     }, this));
        },
        revertChanges: function() {
            this.setState({
                volumes: this.props.volumes.models,
                disks: this.props.disks
            });
        },
        applyChanges: function() {
            var cluster = this.props.cluster;
            if (this.hasValidationErrors()) {
                return (new $.Deferred()).reject();
            }
            return $.when.apply($, this.props.nodes.map(function(node) {
                    node.disks.each(function(disk, index) {
                        disk.set({volumes: new models.Volumes(this.props.disks.at(index).get('volumes').toJSON())});
                    }, this);
                    return Backbone.sync('update', node.disks, {url: _.result(node, 'url') + '/disks'});
                }, this))
                .done(_.bind(function() {
                    cluster.fetch();
                }, this))
                .fail(_.bind(function(response) {
                    //this.checkForChanges();
                    utils.showErrorDialog({
                        title: i18n('cluster_page.nodes_tab.configure_disks.configuration_error.title'),
                        message: utils.getResponseText(response) || i18n('cluster_page.nodes_tab.configure_disks.configuration_error.saving_warning')
                    });
                }, this));
        },
        provideVolumes: function(diskIndex, disk) {
            
            var disks = this.state.disks;
            disks.models[diskIndex] = disk;
            //console.log(this.state.disks, diskIndex, volume);
            //console.log(this.state.disks.models[diskIndex].attributes.volumes);
            //console.log(disks);
            this.setState({
                disks: disks
            });
        },
        mapVolumesColors: function() {
            var volumesColors = {},
                colors = [
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
            this.props.volumes.each(function(volume, index) {
                volumesColors[volume.get('name')] = colors[index];
            }, this);
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
        render: function() {
            var nodes = this.props.nodes,
                disks = this.state.disks,
                volumesColors = this.mapVolumesColors();
            console.log('render page');
            return (
                <div className='edit-node-disks row'>
                    <h3>
                        {i18n('cluster_page.nodes_tab.configure_disks.title', {count: nodes.length, name: nodes.length && nodes.at(0).get('name')})}
                    </h3>
                    <div className="node-disks">
                    </div>
                    {disks && _.map(disks.models, function(disk, index) {
                        return (<NodeDisk
                            disk={disk}
                            index={index}
                            volumes={this.props.volumes.models}
                            diskMetaData={this.getDiskMetaData(disk)}
                            disabled={this.props.disabled}
                            volumesColors={volumesColors}
                            provideVolumes={this.provideVolumes}
                        />);
                    }, this)}

                    <div className='col-xs-12 page-buttons'>
                        <div className='well clearfix'>
                          <div className='btn-group'>
                            <button onClick={this.returnToNodeList} className='btn btn-default btn-return'>{i18n('cluster_page.nodes_tab.back_to_nodes_button')}</button>
                          </div>
                          <div className="btn-group pull-right">
                            <button className="btn btn-default btn-defaults" onClick={this.loadDefaults}>{i18n('common.load_defaults_button')}</button>
                            <button className="btn btn-default btn-revert-changes">{i18n('common.cancel_changes_button')}</button>
                            <button className="btn btn-success btn-apply">{i18n('common.apply_button')}</button>
                          </div>
                        </div>
                    </div>

                    
                </div>
                );
        }
    });

    var NodeDisk = React.createClass({
        mixins: [
            componentMixins.backboneMixin('disk')
        ],
        getInitialState: function() {
            return null;
        },
        volumeStylesTemplate: function(startColor, endColor) {
            return 'background: ' + startColor + '; ' +
                'background: -moz-linear-gradient(top, ' + startColor + ' 0%, ' + endColor + ' 100%); ' +
                'background: -webkit-gradient(linear, left top, left bottom, color-stop(0%,' + startColor + '), color-stop(100%,' + endColor + ')); ' +
                'background: -webkit-linear-gradient(top, ' + startColor + ' 0%, ' + endColor + ' 100%); ' +
                'background: -o-linear-gradient(top, ' + startColor + ' 0%, ' + endColor + ' 100%); ' +
                'background: -ms-linear-gradient(top, ' + startColor + ' 0%, ' + endColor + ' 100%); ' +
                'background: linear-gradient(to bottom, ' + startColor + ' 0%, ' + endColor + ' 100%); ' +
                'bfilter: progid:DXImageTransform.Microsoft.gradient(startColorstr=' + startColor + ', endColorstr=' + endColor + ', GradientType=0);';
        },
        handleVolumeSize: function(e) {
            var volumesInfo = this.state.volumesInfo,
                disk = this.state.disk;
            volumesInfo[e.target.name] = parseInt(e.target.value);
            disk.get('volumes').each(function(volume, index) {
                if (e.target.name == volume.get('name')) {
                    volume.set({size: volumesInfo[volume.get('name')]}, {validate: true, minimum: this.props.volumes[index].get('min_size'), maximum: {disk: disk, volume: volume}})
                }
            }, this);
            this.setState({disk: disk});
        },
        renderVolume: function(name, width, size) {
            $(this.refs['volume_' + name].getDOMNode())
                .css('width', width + '%')
                .find('.volume-group-size').text(utils.showDiskSize(size, 2));
        },
        renderVisualGraph: function() {
            var disk = this.props.disk;
            if (!disk.get('volumes').some('validationError') && disk.isValid()) {
                var unallocatedWidth = 100;
                disk.get('volumes').each(function(volume) {
                    var width = disk.get('size') ? utils.floor(volume.get('size') / disk.get('size') * 100, 2) : 0;
                    unallocatedWidth -= width;
                    this.renderVolume(volume.get('name'), width, volume.get('size'));
                }, this);
                this.renderVolume('unallocated', unallocatedWidth, disk.getUnallocatedSpace());
            }
        },
        applyColors: function() {
            this.props.disk.get('volumes').each(function(volume) {
                var name = volume.get('name'),
                    colors = this.props.volumesColors[name],
                    style = $(this.refs['volume_' + name].getDOMNode()).attr('style');
                $(this.refs['volume_' + name].getDOMNode()).attr('style', style + ' ' + this.volumeStylesTemplate(_.first(colors), _.last(colors)));
                $(this.refs['volume-group-flag_' + name].getDOMNode()).attr('style', this.volumeStylesTemplate(_.first(colors), _.last(colors)));
            }, this);
        },
        getVolumesInfo: function() {
            var volumes = {};
            _.each(this.props.volumes, function(volume) {
                volumes[volume.get('name')] = this.props.disk.get('volumes').findWhere({name: volume.get('name')}).get('size') || 0;
            }, this);
            return volumes;
        },
        componentWillMount: function() {
            this.setState({
                disk: this.props.disk,
                volumes: this.props.volumes,
                volumesInfo: this.getVolumesInfo()
            });
        },
        componentWillReceiveProps: function() {
            // console.log('componentWillReceiveProps');
            // this.setState({
            //     disk: this.props.disk,
            //     volumes: this.props.volumes,
            //     volumesInfo: this.getVolumesInfo()
            // });
        },
        // componentWillUpdate: function() {
        //     console.log('componentWillUpdate');
        // },
        componentDidUpdate: function() {
            this.renderVisualGraph();
        },
        componentDidMount: function() {
            this.renderVisualGraph();
            this.applyColors();
        },
        render: function() {
            console.log('render disk');
            var disk = this.state.disk,
                volumes = this.state.volumes,
                diskMetaData = this.props.diskMetaData,
                locked = this.props.disabled,
                sortOrder = ['name', 'model', 'size'];
            return (
                <div className="col-xs-12 disk-box" data-disk={disk.id}>
                    <div className="row">
                        <h4 className="col-xs-6">
                            {disk.get('name')} ({disk.id})
                        </h4>
                        <h4 className="col-xs-6 text-right">
                            {i18n('cluster_page.nodes_tab.configure_disks.total_space')} : {utils.showDiskSize(disk.get('size'), 2)}
                        </h4>
                    </div>

                    <div className="row disk-visual clearfix" data-toggle="collapse" data-target={'#' + disk.get('name')}>
                        {_.map(volumes, function(volume) {
                            return (
                                <div className={'volume-group pull-left ' + volume.get('name')} ref={'volume_' + volume.get('name')} style={{width: 0}}>
                                    <div className="text-center">
                                    <div>{volume.get('label')}</div>
                                    <div className="volume-group-size">{utils.showDiskSize(0)}</div>
                                </div>
                                <div className="close-btn hide">&times;</div>
                                </div>
                            );
                        })}
                        <div className="volume-group pull-left" ref={'volume_unallocated'} style={{width: '100%'}}>
                            <div className="text-center">
                                <div className="volume-group-name">{i18n('cluster_page.nodes_tab.configure_disks.unallocated')}</div>
                                <div className="volume-group-size">{utils.showDiskSize(disk.get('size'), 2)}</div>
                            </div>
                        </div>
                    </div>

                    <div className="row collapse disk-details" id={disk.get('name')}>
                        
                        <div className="col-xs-6">
                            {diskMetaData &&
                                <div>
                                <h5>{i18n('cluster_page.nodes_tab.configure_disks.disk_information')}</h5>
                                <div className="form-horizontal disk-info-box">
                                    {_.map(utils.sortEntryProperties(diskMetaData, sortOrder), function(propertyName) {
                                        return (
                                            <div className="form-group">
                                                <label className="col-xs-2">{propertyName.replace(/_/g, ' ')}</label>
                                                <div className="col-xs-10">
                                                    <p className="form-control-static">
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

                        <div className="col-xs-6">
                            <h5 data-i18n="cluster_page.nodes_tab.configure_disks.volume_groups"></h5>
                            <div className="form-horizontal disk-utility-box">
                                {volumes && _.map(volumes, function(volume) {
                                    var volumeName = volume.get('name');
                                    return (
                                        <div>
                                          <div className="form-group volume-group" data-volume={volumeName}>
                                            <label className="col-xs-4">
                                                <span ref={'volume-group-flag_' + volumeName}>&nbsp;</span>
                                                {volume.get('label')}
                                            </label>
                                            <div className="col-xs-3 volume-group-use-all-allowed-btn">
                                                {locked &&
                                                    <button className="btn btn-link">
                                                        {i18n('cluster_page.nodes_tab.configure_disks.use_all_allowed_space')}
                                                    </button>
                                                }
                                            </div>
                                            <div className="col-xs-4 volume-group-input">
                                                <input
                                                    type="range"
                                                    onChange={this.handleVolumeSize}
                                                    min='0'
                                                    name={volumeName}
                                                    max={disk.get('size')}
                                                    value={disk.get('volumes').findWhere({name: volume.get('name')}).get('size') || 0}/>
                                                <input
                                                    id={disk.id + '-' + volume.get('name')}
                                                    type="text"
                                                    className="form-control"
                                                    name={volumeName}
                                                    value={disk.get('volumes').findWhere({name: volume.get('name')}).get('size') || 0}
                                                    onChange={this.handleVolumeSize}
                                                />
                                            </div>
                                            <div className="col-xs-1 volume-group-size-label">{i18n('common.size.mb')}</div>
                                          </div>
                                          <div className="volume-group-error text-red text-right"></div>
                                        </div>
                                    );
                                }, this)}
                                <div className="volume-group-error common text-red text-right"></div>
                              </div>
                        </div>
                    </div>
                </div>
            );
        }
    });

    return EditNodeDisksScreen;
});
