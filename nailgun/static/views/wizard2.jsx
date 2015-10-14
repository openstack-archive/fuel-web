/*
 * Copyright 2014 Mirantis, Inc.
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
        'require',
        'jquery',
        'underscore',
        'i18n',
        'react',
        'utils',
        'models',
        'jsx!component_mixins',
        'jsx!views/dialogs'
    ],
    function(require, $, _, i18n, React, utils, models, componentMixins, dialogs) {
        'use strict';

        var clusterWizardPanes = [];

        var CommonControl = React.createClass({
            render: function() {
                return (
                    <div className={this.props.classes}>
                        <label className="parameter-box clearfix col-xs-12" disabled={this.props.disabled}>
                            <div className="parameter-control col-xs-1">
                                <div className="custom-tumbler">
                                    <input type={this.props.type} name={this.props.pane}
                                           value={this.props.value}/>
                                    <span>&nbsp;</span>
                                </div>
                            </div>
                            <div className="parameter-name col-xs-0">{this.props.label}</div>
                        </label>
                        {
                            this.props.hasDescription &&
                            <div className="modal-parameter-description col-xs-offset-1">
                                {this.props.description}
                            </div>
                        }
                    </div>
                );
            }
        });

        var CreateCluster =  React.createClass({
            mixins: [
                componentMixins.backboneMixin('releases'),
                componentMixins.backboneMixin('wizard')
            ],
            getActivePane: function() {
                var pane = this.props.panes[this.props.activePaneIndex];
                return pane || {};
            },
            render: function() {
                console.log('render CreateClusterWizard', this.props, this.state);
                var activeIndex = this.props.activePaneIndex,
                    nextStyle = this.props.nextAvailable ? {display: 'inline-block'} : {display: 'none'},
                    createStyle = this.props.createEnabled ? {display: 'inline-block'} : {display: 'none'};
                return (
                    <div className="modal fade create-cluster-modal">
                        <div id="wizard" className="modal-dialog">
                            <div className="modal-content">
                                <div className="modal-header">
                                    <button type="button" className="close" aria-label="Close"
                                            data-dismiss="modal">
                                        <span aria-hidden="true">×</span>
                                    </button>
                                    <h4 className="modal-title">{i18n('dialog.create_cluster_wizard.title')}</h4>
                                </div>
                                <div className="modal-body wizard-body">
                                    <div className="wizard-steps-box">
                                        <div className="wizard-steps-nav col-xs-3">
                                            <ul className="wizard-step-nav-item nav nav-pills nav-stacked">
                                                {
                                                    this.props.panes.map(function(pane, i) {
                                                        var classes = utils.classNames('wizard-step', {
                                                            disabled: i > activeIndex,
                                                            available: i < activeIndex,
                                                            active: i == activeIndex
                                                        });
                                                        return (
                                                            <li key={pane.title} role="wizard-step"
                                                                className={classes}>
                                                                <a onClick={_.bind(function(){this.goToPane(i);},this)}>{pane.title}</a>
                                                            </li>
                                                        );
                                                    }, this)
                                                }
                                            </ul>
                                        </div>
                                        <div className="pane-content col-xs-9">
                                            {
                                                React.createElement(this.getActivePane().view, this.props)
                                            }
                                        </div>
                                        <div className="clearfix"></div>
                                    </div>
                                </div>

                                <div className="modal-footer wizard-footer">
                                    <button className="btn btn-default pull-left" data-dismiss="modal">
                                        {i18n('common.cancel_button')}
                                    </button>
                                    <button
                                        className={utils.classNames("btn btn-default prev-pane-btn",{disabled:!this.props.previousAvailable})}
                                        onClick={this.props.prevPane}>
                                        <span className="glyphicon glyphicon-arrow-left"
                                              aria-hidden="true"></span>
                                        <span>{i18n('dialog.create_cluster_wizard.prev')}</span>
                                    </button>
                                    <button className="btn btn-default btn-success next-pane-btn"
                                            style={nextStyle}
                                            onClick={this.props.nextPane}>
                                        <span>{i18n('dialog.create_cluster_wizard.next')}</span>
                                        <span className="glyphicon glyphicon-arrow-right"
                                              aria-hidden="true"></span>
                                    </button>
                                    <button className="btn btn-default btn-success finish-btn"
                                            style={createStyle}>
                                        {i18n('dialog.create_cluster_wizard.create')}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            }
        });

        var NameRelease = React.createClass({
            render: function() {
                if(!this.props.releases || !this.props.wizard) {
                    return null;
                }
                var releases = this.props.releases;
                var props = this.props;
                var nameAndRelease = props.wizard.get('NameAndRelease')
                return (
                    <form className="form-horizontal create-cluster-form"
                          onSubmit={function() {return false;}}
                          autoComplete="off">
                        <fieldset>
                            <div className="form-group">
                                <label
                                    className="control-label col-xs-3">{i18n('dialog.create_cluster_wizard.name_release.name')}</label>

                                <div className="controls col-xs-9">
                                    <input type="text" className="form-control" name="name" maxLength="50" value={nameAndRelease.name}
                                           autofocus onChange={function(val) {props.onChange('NameAndRelease', 'name', val)}}/>
                                    <span className="help-block"></span>
                                </div>
                            </div>
                            <div className="form-group">
                                <label
                                    className="control-label col-xs-3">{i18n('dialog.create_cluster_wizard.name_release.release_label')}</label>

                                <div className="controls col-xs-9 has-warning">
                                    <select className="form-control" name="release">
                                        {
                                            releases.map(function(release) {
                                                return <option>{release.get('name')}</option>
                                            })
                                        }
                                    </select>
                                    { this.props.connectivityAlert && <div
                                        className="alert alert-warning alert-nailed">{ this.props.connectivityAlert}</div> }
                                    <div className="release-description">{this.props.releaseDescription}</div>
                                </div>
                            </div>
                        </fieldset>
                    </form>
                );
            }
        });
        clusterWizardPanes.push({view: NameRelease, title: i18n('dialog.create_cluster_wizard.name_release.title')
        });

        var Mode = React.createClass({
            render: function() {
                return <div>Under Construction</div>;
            }
        });
        clusterWizardPanes.push({view: Mode, title: i18n('dialog.create_cluster_wizard.mode.title'), hidden: true});

        var Compute = React.createClass({
            render: function() {
                return (
                    <form className="form-horizontal wizard-compute-pane"
                          onSubmit={function() {return false;}}>
                        <fieldset>
                            <div className="form-group">
                                {
                                    this.props.hypervisors.map(function(hypervisor) {
                                        return (
                                            <CommonControl
                                                name={hypervisor.name}
                                                type='checkbox'
                                                value="value"
                                                label={hypervisor.name}
                                                description={hypervisor.desc}
                                                hasDescription={true}
                                                />
                                        );
                                    })
                                }
                            </div>
                        </fieldset>
                    </form>
                );
            }
        });
        clusterWizardPanes.push({view: Compute, title: i18n('dialog.create_cluster_wizard.compute.title')});

        var Network = React.createClass({
            render: function() {
                return (
                    <form className="form-horizontal wizard-network-pane"
                          onSubmit={function() {return false;}}>
                        <fieldset>
                            {
                                false &&
                                <div className="network-pane-description">
                                    {i18n('dialog.create_cluster_wizard.network.description')}
                                    <a href={require('utils').composeDocumentationLink('planning-guide.html#choose-network-topology')}
                                       target="_blank">
                                        {i18n('dialog.create_cluster_wizard.network.description_link')}
                                    </a>
                                </div>
                            }
                            <div className="form-group">
                                {
                                    this.props.networks.map(function(network) {
                                        return (
                                            <div>
                                                <CommonControl
                                                    name={network.name}
                                                    type='radio'
                                                    value="value"
                                                    label={network.name}
                                                    description={network.desc}
                                                    hasDescription={true}
                                                    />
                                                {
                                                    network.drivers && network.drivers.map(function(driver) {
                                                        return (
                                                            <CommonControl
                                                                classes="ml2-driver"
                                                                name={driver.name}
                                                                type='checkbox'
                                                                value="value"
                                                                label={driver.name}
                                                                description={driver.desc}
                                                                hasDescription={true}
                                                                />
                                                        );
                                                    })
                                                }
                                            </div>
                                        );
                                    })
                                }
                            </div>
                        </fieldset>
                    </form>
                );
            }
        });
        clusterWizardPanes.push({view: Network, title: i18n('dialog.create_cluster_wizard.network.title')});

        var Storage = React.createClass({
            render: function() {
                return (
                    <form className="form-horizontal" oonSubmit={function() {return false;}}>
                        <fieldset>
                            <div className="form-group">
                                <div className="ceph col-xs-12">
                                    <h5>{i18n('dialog.create_cluster_wizard.storage.ceph_description')}</h5>

                                    <p className="modal-parameter-description col-xs-12">{i18n('dialog.create_cluster_wizard.storage.ceph_help')}</p>
                                </div>
                            </div>
                        </fieldset>
                    </form>
                );
            }
        });
        clusterWizardPanes.push({view: Storage, title: i18n('dialog.create_cluster_wizard.storage.title')});

        var AdditionalServices = React.createClass({
            render: function() {
                return (
                    <form className="form-horizontal wizard-compute-pane"
                          onSubmit={function() {return false;}}>
                        <fieldset>
                            <div className="form-group">
                                {
                                    this.props.addons.map(function(hypervisor) {
                                        return (
                                            <CommonControl
                                                name={hypervisor.name}
                                                type='checkbox'
                                                value="value"
                                                label={hypervisor.name}
                                                description={hypervisor.desc}
                                                hasDescription={true}
                                                />
                                        );
                                    })
                                }
                            </div>
                        </fieldset>
                    </form>
                );
            }
        });
        clusterWizardPanes.push({view: AdditionalServices, title: i18n('dialog.create_cluster_wizard.additional.title')});

        var Finish = React.createClass({
            render: function() {
                return (
                    <p>
                        <span>{i18n('dialog.create_cluster_wizard.ready.env_select_deploy')} </span>
                        <b>{i18n('dialog.create_cluster_wizard.ready.deploy')} </b>
                        <span>{i18n('dialog.create_cluster_wizard.ready.or_make_config_choice')} </span>
                        <b>{i18n('dialog.create_cluster_wizard.ready.env')} </b>
                        <span>{i18n('dialog.create_cluster_wizard.ready.console')}</span>
                    </p>

                );
            }
        });
        clusterWizardPanes.push({view: Finish, title: i18n('dialog.create_cluster_wizard.ready.title')});

        var CreateClusterWizard = React.createClass({
            statics: {
                show: function(options) {
                    return utils.universalMount(this, options, $('#modal-container'));
                }
            },
            getInitialState: function() {
                return {
                    activePaneIndex: 0,
                    maxAvailablePaneIndex: 0,
                    panes: clusterWizardPanes,
                    previousAvailable: true,
                    nextAvailable: true,
                    createEnabled: false
                }
            },
            componentWillMount: function() {
                this.config = {
                    NameAndRelease: {
                        name: {
                            type: 'custom',
                            value: '',
                            bind: 'cluster:name'
                        },
                        release: {
                            type: 'custom',
                            bind: {id: 'cluster:release'},
                            aliases: {
                                operating_system: 'NameAndRelease.release_operating_system',
                                roles: 'NameAndRelease.release_roles',
                                name: 'NameAndRelease.release_name'
                            }
                        }
                    }
                };

                this.wizard = new models.WizardModel(this.config);
                this.cluster = new models.Cluster();
                this.settings = new models.Settings();
                this.releases = this.wizard.releases || new models.Releases();

                this.wizard.processConfig(this.config);

                this.configModels = _.pick(this, 'settings', 'cluster', 'wizard');
                this.configModels.default = this.wizard;
            },
            componentDidMount: function() {
                //Backbone.history.on('route', this.close, this);

                this.setState(_.pick(this, 'wizard', 'cluster', 'settings', 'releases'), function() {
                    this.releases.fetch().done(_.bind(function() {
                    }, this));
                });

                var $el = $(this.getDOMNode());
                $el.on('hidden.bs.modal', this.handleHidden);
                $el.on('shown.bs.modal', function() {
                    $el.find('[autofocus]:first').focus();
                });
                $el.modal(_.defaults(
                    {keyboard: false},
                    _.pick(this.props, ['background', 'backdrop']),
                    {background: true, backdrop: true}
                ));

                this.updateButtonsState();
            },
            componentWillUnmount: function() {
                //Backbone.history.off(null, null, this);
                componentMixins.backboneMixin.off(this);

                $(this.getDOMNode()).off('shown.bs.modal hidden.bs.modal');
                //this.rejectResult();
            },
            handleHidden: function() {
                React.unmountComponentAtNode(this.getDOMNode().parentNode);
            },
            updateButtonsState: function() {
                var numberOfPanes = this.getEnabledPanes().length;
                this.setState({
                    previousAvailable: this.state.activePaneIndex > 0,
                    nextAvailable: this.state.activePaneIndex < numberOfPanes - 1,
                    createEnabled: this.state.activePaneIndex == numberOfPanes - 1
                });
            },
            getEnabledPanes: function() {
                var res = this.state.panes.filter(function(pane, i) {
                    return !pane.hidden;
                });
                return res;
            },
            prevPane: function() {
                this.setState({activePaneIndex: --this.state.activePaneIndex});
                this.updateButtonsState();
            },
            nextPane: function() {
                this.setState({activePaneIndex: ++this.state.activePaneIndex});
                this.updateButtonsState();
            },
            gotToPane: function() {

            },
            updateConfig: function(config) {
                var name = this.wizard.get('NameAndRelease.name');
                var release = this.wizard.get('NameAndRelease.release');
                _.extend(this.wizard.config, _.cloneDeep(config));
                this.wizard.off(null, null, this);
                //this.wizard.processPaneRestrictions();
                this.wizard.initialize(this.wizard.config);
                this.wizard.processConfig(this.wizard.config);
                this.wizard.set({
                    'NameAndRelease.name': name,
                    'NameAndRelease.release': release
                });
                this.setState({
                    activePaneIndex: 0,
                    maxAvailablePaneIndex: 0,
                });
                //this.wizard.processRestrictions();
            },
            onChange(pane, field, event) {
                console.log('onChange', pane, field, event.target.value);
                if(pane="NameAndRelease") {
                    if(field=='name') {
                        this.wizard.set('NameAndRelease.name', event.target.value);
                    }
                }
            },
            render: function() {
                return (
                    <CreateCluster
                        {...this.state}
                        onChange={this.onChange}
                        nextPane={this.nextPane}
                        prevPane={this.prevPane}
                        goToPane={this.goToPane}
                    />
                );
            }
        });

        return {
            CreateClusterWizard: CreateClusterWizard
        };
    });
