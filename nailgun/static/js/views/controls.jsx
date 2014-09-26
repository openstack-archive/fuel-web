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
    'jquery',
    'underscore',
    'react',
    'jsx!views/input'
],
function($, _, React, Input) {
    'use strict';

    var controls = {},
        cx = React.addons.classSet;

    controls.SelectAllCheckbox = React.createClass({
        //FIXME: use Input
        getDefaultProps: function() {
            return {type: 'checkbox'};
        },
        render: function() {
            return (
                <div className={cx(_.extend({'select-all': true}, this.props.cs.common))}>
                    <label className={cx(this.props.cs.label)}>
                        {this.renderInput()}
                        <span>&nbsp;</span>
                        <span>{$.t('common.select_all_button')}</span>
                    </label>
                </div>
            );
        }
    });

    controls.RadioGroup = React.createClass({
        //FIXME: use Input
        propTypes: {
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            hiddenValues: React.PropTypes.arrayOf(React.PropTypes.string),
            disabledValues: React.PropTypes.arrayOf(React.PropTypes.string),
            valueWarnings: React.PropTypes.object
        },
        render: function() {
            return (
                <div className={cx(this.props.cs.common)}>
                    {this.renderLabel()}
                    <form onChange={this.onChange}>
                        {_.map(this.props.values, function(value) {
                            if (!_.contains(this.props.hiddenValues, value.data)) {
                                return this.transferPropsTo(
                                    <controls.RadioButton
                                        key={value.data}
                                        value={this.props.value}
                                        disabled={this.props.disabled || _.contains(this.props.disabledValues, value.data)}
                                        tooltipText={this.props.valueWarnings[value.data].join(' ')}
                                    />
                                );
                            }
                        }, this)}
                    </form>
                </div>
            );
        }
    });

    controls.ToggleablePassword = React.createClass({
        //FIXME: use Input
        getInitialState: function() {
            return {visible: false};
        },
        togglePassword: function() {
            if (this.props.disabled) { return; }
            this.setState({visible: !this.state.visible});
        },
        render: function() {
            return (
                <div className={cx(_.extend({'parameter-box': true, clearfix: true}, this.props.cs.common))}>
                    {this.renderLabel()}
                    <div className={cx({'parameter-control': true, 'input-append': this.props.toggleable})}>
                        {this.renderInput(this.state.visible ? 'text' : 'password')}
                        {this.props.toggleable &&
                            <span className='add-on' onClick={this.togglePassword}>
                                <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                            </span>
                        }
                    </div>
                    {this.renderDescription()}
                </div>
            );
        }
    });

    controls.ProgressBar = React.createClass({
        render: function() {
            return (
                <div className='progress-bar'>
                    <div className='progress progress-striped progress-success active'>
                        <div className='bar'/>
                    </div>
                </div>
            );
        }
    });

    controls.Table = React.createClass({
        //FIXME: try without cs
        render: function() {
            var tableClasses = {
                table: true,
                'table-bordered': true,
                'table-striped': true
            };
            return (
                <table className={cx(_.extend(tableClasses, this.props.cs.table))}>
                    <thead>
                        <tr>
                            {_.map(this.props.head, function(column, index) {
                                return <th key={index} className={column.className || ''}>{column.label}</th>;
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {_.map(this.props.body, function(row, rowIndex) {
                            return <tr key={rowIndex}>
                                {_.map(row, function(column, columnIndex) {
                                    return <td key={columnIndex} className='enable-selection'>{column}</td>;
                                })}
                            </tr>;
                        })}
                    </tbody>
                </table>
            );
        }
    });

    return controls;
});
