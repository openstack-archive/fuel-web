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
        'jsx!views/dialogs'
    ],
    function(require, $, _, i18n, React, utils, models, dialogs) {
        'use strict';

        var CommonControl = React.createClass({
            render: function() {
                console.log('render CommonControl props=', this.props);
                return (
                    <div>
                        <label className="parameter-box clearfix col-xs-12" disabled={this.props.disabled}>
                            <div className="parameter-control col-xs-1">
                                <div className="custom-tumbler">
                                    <input type={this.props.type} name={this.props.pane} value={this.props.value}/>
                                    <span>&nbsp;</span>
                                </div>
                            </div>
                            <div className="parameter-name col-xs-0">{this.props.label}</div>
                        </label>
                        {
                            this.props.hasDescription &&
                            <div className="modal-parameter-description col-xs-offset-1">{this.props.description}</div>
                        }
                    </div>
                );
            }
        });


        var NameRelease = React.createClass({
            render: function() {
                return (
                    <form className="form-horizontal create-cluster-form" onsubmit="return false"
                          autoComplete="off">
                        <fieldset>
                            <div className="form-group">
                                <label
                                    className="control-label col-xs-3">{i18n('dialog.create_cluster_wizard.name_release.name')}</label>

                                <div className="controls col-xs-9">
                                    <input type="text" className="form-control" name="name" maxLength="50"
                                           autofocus/>
                                    <span className="help-block"></span>
                                </div>
                            </div>
                            <div className="form-group">
                                <label
                                    className="control-label col-xs-3">{i18n('dialog.create_cluster_wizard.name_release.release_label')}</label>

                                <div className="controls col-xs-9 has-warning">
                                    <select className="form-control" name="release">
                                        {
                                            this.props.releases.map(function(release) {
                                                return <option>{release.name}</option>
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

        var Mode = React.createClass({
            render: function() {
                return <div>Under Construction</div>;
            }
        });

        var Compute = React.createClass({
            render: function() {
                console.log('render Compute props=', this.props);
                return (
                    <form className="form-horizontal" onsubmit="return false">
                        <fieldset>
                            <div className="form-group">
                                {
                                    this.props.hypervisors.map(function(hypervisor){
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

        var views = {},
            clusterWizardPanes = [
                {view: NameRelease, title: i18n('dialog.create_cluster_wizard.name_release.title')},
                //{view: Mode, title: i18n('dialog.create_cluster_wizard.mode.title'},
                {view: Compute, title: i18n('dialog.create_cluster_wizard.compute.title')},
                {view: NameRelease, title: i18n('dialog.create_cluster_wizard.network.title')},
                {view: NameRelease, title: i18n('dialog.create_cluster_wizard.storage.title')},
                {view: NameRelease, title: i18n('dialog.create_cluster_wizard.additional.title')},
                {view: NameRelease, title: i18n('dialog.create_cluster_wizard.ready.title')}
            ];

        views.CreateClusterWizard = React.createClass({
            statics: {
                show: function(options) {
                    return utils.universalMount(this, options, $('#modal-container'));
                }
            },
            getInitialState: function() {
                return {
                    activePaneIndex: 0,
                    panes: clusterWizardPanes,
                    releases: [
                        {name: 'Oppa Release 1'},
                        {name: 'Oppa Release 2'},
                    ],
                    hypervisors: [
                        {name: 'Oppa Hyper1', desc:'Oppa Hyper1 Description'},
                        {name: 'Oppa Hyper2', desc:'Oppa Hyper3 Description'},
                        {name: 'Oppa Hyper3', desc:'Oppa Hyper3 Description'}
                    ],
                    connectivityAlert: 'Oppa Connectivity alert',
                    releaseDescription: 'Oppa Release Description',
                    createEnabled: false
                }
            },
            componentDidMount: function() {
                //Backbone.history.on('route', this.close, this);
                var $el = $(this.getDOMNode());
                console.log('$el is', $el);
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
                $(this.getDOMNode()).off('shown.bs.modal hidden.bs.modal');
                //this.rejectResult();
            },
            handleHidden: function() {
                React.unmountComponentAtNode(this.getDOMNode().parentNode);
            },
            updateButtonsState: function() {
                this.setState({
                    previousAvailable: this.state.activePaneIndex > 0,
                    nextAvailable: this.state.activePaneIndex < this.state.panes.length - 1,
                    createEnabled: this.state.activePaneIndex == this.state.panes.length - 1
                })
            },
            getActivePane: function() {
                var res = this.state.panes.filter(function(pane, i) {
                    return i == this.state.activePaneIndex;
                }, this);
                console.log('active pane=', res);
                return res.length > 0 && res[0];
            },
            goPreviousPane: function() {
                this.setState({activePaneIndex: --this.state.activePaneIndex});
                this.updateButtonsState();
            },
            goNextPane: function() {
                this.setState({activePaneIndex: ++this.state.activePaneIndex});
                this.updateButtonsState();
            },
            render: function() {
                console.log('render new');
                var activeIndex = this.state.activePaneIndex,
                    nextStyle = this.state.nextAvailable ? {display: 'inline-block'} : {display: 'none'},
                    createStyle = this.state.createEnabled ? {display: 'inline-block'} : {display: 'none'};
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
                                                    this.state.panes.map(function(pane, i) {
                                                        console.log(arguments);
                                                        var classes = utils.classNames('wizard-step', {
                                                            disabled: i > activeIndex,
                                                            available: i < activeIndex,
                                                            active: i == activeIndex
                                                        });
                                                        return (
                                                            <li role="wizard-step" className={classes}>
                                                                <a onClick={_.bind(function(){this.goToPane(i);},this)}>{pane.title}</a>
                                                            </li>
                                                        );
                                                    }, this)
                                                }
                                            </ul>
                                        </div>
                                        <div className="pane-content col-xs-9">
                                            { React.createElement(this.getActivePane().view, this.state) }
                                        </div>
                                        <div className="clearfix"></div>
                                    </div>
                                </div>

                                <div className="modal-footer wizard-footer">
                                    <button className="btn btn-default pull-left" data-dismiss="modal">
                                        {i18n('common.cancel_button')}
                                    </button>
                                    <button
                                        className={utils.classNames("btn btn-default prev-pane-btn",{disabled:!this.state.previousAvailable})}
                                        onClick={this.goPreviousPane}>
                                        <span className="glyphicon glyphicon-arrow-left"
                                              aria-hidden="true"></span>
                                        <span>{i18n('dialog.create_cluster_wizard.prev')}</span>
                                    </button>
                                    <button className="btn btn-default btn-success next-pane-btn" style={nextStyle}
                                            onClick={this.goNextPane}>
                                        <span>{i18n('dialog.create_cluster_wizard.next')}</span>
                                        <span className="glyphicon glyphicon-arrow-right"
                                              aria-hidden="true"></span>
                                    </button>
                                    <button className="btn btn-default btn-success finish-btn" style={createStyle}>
                                        {i18n('dialog.create_cluster_wizard.create')}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            }
        });

        console.log('new views', views);
        return views;
    });
