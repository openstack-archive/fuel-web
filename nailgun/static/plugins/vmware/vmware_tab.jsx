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
    'jsx!controls',
    'jsx!component_mixins',
    'plugins/vmware/vmware_models'
], function(React, controls, componentMixins, VmwareModels) {
    'use strict';

    var testMeta = [
        {name: 'firstName', label: 'First Name', description: 'First Name Desc'},
        {name: 'lastName', label: 'Last Name', description: 'Last Name Desc'}
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
                    <FieldGroup meta={testMeta} instance={testInstance}/>
                    <div style={{'margin-left': '100px'}}>
                    <FieldGroup meta={testMeta} instance={testInstance}/>
                    </div>
                    <FieldGroup meta={testMeta} instance={testInstance}/>
                </div>
            );
        }
    });

    var Network = React.createClass({
        render: function() {
            return (
                <div className="network">
                    <legend className="vmware">{$.t('vmware.network')}</legend>
                    <FieldGroup meta={testMeta} instance={testInstance}/>
                </div>
            );
        }
    });

    var Glance = React.createClass({
        render: function() {
            return (
                <div className="glance">
                    <legend className="vmware">{$.t('vmware.glance')}</legend>
                    <FieldGroup meta={testMeta} instance={testInstance}/>
                </div>
            );
        }
    });

    return React.createClass({
        componentWillMount: function() {
            this.clusterId = this.props.cluster.id;
            this.model = new VmwareModels.VCenter({az: 'sx', id: this.clusterId});
            console.log('@@@', this.model);
            //this.updateData();

            console.log('WILL MOUNT', this);
        },
        updateData: function() {
            this.model.fetch();
        },
        render: function() {
            console.log('OPPA', this.props);
            var z = 'Oppa';
            return (
                <div className="vmware">
                    <div className="wrapper">
                        <h3>{$.t('vmware.title')}</h3>
                        <AvailabilityZones/>
                        <Network/>
                        <Glance/>
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
