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
    'react',
    'jquery',
    'jsx!views/controls',
    'jsx!component_mixins',
    'plugins/vmware/vmware_models'
], function(React, $, controls, componentMixins, VmwareModels) {
    'use strict';

    var azMeta = [
        {name: 'Availability Zone name', label: 'Availability Zone name', description: 'Availability Zone name'},
        {name: 'vCenter host', label: 'vCenter host', description: 'vCenter host'},
        {name: 'vCenter username', label: 'vCenter username', description: 'vCenter username'},
        {name: 'vCenter password', label: 'vCenter password', description: 'vCenter password'}
    ];
    var computeMeta = [
        {name: 'vSphere Cluster', label: 'vSphere Cluster', description: 'vSphere Cluster'},
        {name: 'Service Name', label: 'Service Name', description: 'Service Name'},
        {name: 'DataStore RegEx', label: 'DataStore RegEx', description: 'DataStore RegEx'}
    ];
    var cinderMeta = [
        {name: 'Enable Cinder', label: 'Enable Cinder', description: '', type: 'checkbox'}
    ];
    var networkMeta = [
        {name: 'ESXi VLAN Interface', label: 'ESXi VLAN Interface', description: 'ESXi VLAN Interface'}
    ];
    var glanceMeta = [
        {name: 'vCenter host', label: 'vCenter host', description: 'vCenter host'},
        {name: 'vCenter username', label: 'vCenter username', description: 'vCenter username'},
        {name: 'vCenter password', label: 'vCenter password', description: 'vCenter password'},
        {name: 'DataCenter', label: 'DataCenter', description: 'DataStore'},
        {name: 'DataStore', label: 'DataStore', description: 'DataStore'}
    ];
    var testInstance = {
        firstName: 'Anton',
        lastName: 'Zemlyanov',
        get: function(name) {
            return this[name];
        }
    };

    var Field = React.createClass({
        render: function() {
            var key = this.props.key;
            var meta = this.props.meta;
            var options = this.props.options || [];
            return (
                <div key={meta.name} className="settings-group table-wrapper parameter-box">
                    <controls.Input
                        name={meta.name}
                        type={meta.type || 'text'}
                        label={meta.label}
                        value={this.props.instance.get(meta.name) || ''}
                        description={meta.description}
                        toggleable={meta.type == 'password' ? true : false}
                        wrapperClassName="tablerow-wrapper"
                        onChange={_.bind(function(name, val) {
                            onChange(meta.name, name, val)
                        }, this)}
                        disabled={ this.props.isNew ? false : meta.lockOnEdit }
                    >
                        {options.map(function(index) {
                            return <option key={Math.random()} value={index.value}>{index.label}</option>
                        }, this)}
                    </controls.Input>
                </div>
            );
        }
    });

    var FieldGroup = React.createClass({
        render: function() {
            console.log('FieldGroup props=', this.props);
            var fields = this.props.meta.map(function(meta, index) {
                return (
                    <Field meta={meta} instance={this.props.instance}/>
                );
            }, this);
            return (
                <div>
                    {fields}
                </div>
            );
        }
    });

    var AvailabilityZones = React.createClass({
        render: function() {
            return (
                <div className="availability-zones">
                    <legend className="vmware">{$.t('vmware.availability_zones')}</legend>
                    <FieldGroup meta={azMeta} instance={testInstance}/>
                    <div style={{'margin-left': '40px'}}>
                        <legend className="vmware">Nova Computes:</legend>
                        <h4><i className="icon-plus-circle"></i><i className="icon-minus-circle"></i>&nbsp;Compute 1</h4>
                        <FieldGroup meta={computeMeta} instance={testInstance}/>
                        <hr/>
                        <h4><i className="icon-plus-circle"></i><i className="icon-minus-circle"></i>&nbsp;Compute 2</h4>
                        <FieldGroup meta={computeMeta} instance={testInstance}/>
                    </div>
                    <div style={{'margin-left': '0px'}}>
                        <legend className="vmware">{$.t('vmware.cinder')}</legend>
                        <FieldGroup meta={cinderMeta} instance={testInstance}/>
                    </div>
                </div>
            );
        }
    });

    var Network = React.createClass({
        render: function() {
            var model = this.props.model;
            console.log('model',model);
            if(!model) {
                return false;
            }
            return (
                <div className="network">
                    <legend className="vmware">{$.t('vmware.network')}</legend>
                    <FieldGroup meta={model.get('metadata')} instance={model}/>
                </div>
            );
        }
    });

    var Glance = React.createClass({
        render: function() {
            var model = this.props.model;
            console.log('model',model);
            if(!model) {
                return false;
            }
            return (
                <div className="glance">
                    <legend className="vmware">{$.t('vmware.glance')}</legend>
                    <FieldGroup meta={model.get('metadata')} instance={model}/>
                </div>
            );
        }
    });

    return React.createClass({
        componentWillMount: function() {
            this.clusterId = this.props.cluster.id;
            this.model = new VmwareModels.VCenter({id: this.clusterId});
            this.setState({model: this.model});
            this.updateData();
            console.log('WILL MOUNT', this);
        },
        updateData: function() {
            console.log('azsx', this.model.fetch());
            this.model.fetch().done( _.bind(function() {
                console.log('this is',this);
                this.setState({model: this.model, ok:1});
            }, this));

        },
        render: function() {
            console.log('=== OPPA render VCenter', this.props);
            var model = this.state.model;
            console.log('model===',JSON.stringify(model.attributes));
            return (
                <div className="vmware">
                    <div className="wrapper">
                        <h3>{$.t('vmware.title')}</h3>
                        <AvailabilityZones/>
                        <Network model={model.get('network')}/>
                        <Glance  model={model.get('glance')}/>
                    </div>
                    <div className="page-control-box">
                        <div className="page-control-button-placeholder">
                            <button className="btn btn-load-defaults">{$.t('vmware.reset_to_defaults')}</button>
                            <button className="btn btn-revert-changes">{$.t('vmware.cancel')}</button>
                            <button className="btn btn-success btn-apply-changes">{$.t('vmware.apply')}</button>
                        </div>
                    </div>
                </div>

            );
        }
    });
});
