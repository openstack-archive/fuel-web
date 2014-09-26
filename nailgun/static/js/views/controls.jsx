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
define(['jquery', 'underscore', 'react', 'jsx!views/input'], function($, _, React, Input) {
    'use strict';

    var controls = {},
        cx = React.addons.classSet;

    controls.RadioGroup = React.createClass({
        propTypes: {
            name: React.PropTypes.string,
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            label: React.PropTypes.renderable,
            labelClassName: React.PropTypes.renderable,
            tooltipText: React.PropTypes.renderable
        },
        componentDidMount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip();
        },
        componentWillUnmount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip('destroy');
        },
        render: function() {
            var labelClasses = {'parameter-name': true};
            labelClasses[this.props.labelClassName] = this.props.labelClassName;
            return (
                <div>
                    {this.props.label &&
                        <label className={cx(labelClasses)}>
                            {this.props.label}
                            {this.props.tooltipText &&
                                <i key='tooltip' ref='tooltip' className='icon-attention text-warning' data-toggle='tooltip' title={this.props.tooltipText} />
                            }
                        </label>
                    }
                    {_.map(this.props.values, function(value) {
                        return this.transferPropsTo(
                            <Input
                                key={value.data}
                                type='radio'
                                value={value.data}
                                defaultChecked={value.checked}
                                label={value.label}
                                description={value.description}
                                disabled={value.disabled}
                                tooltipText={value.tooltipText}
                            />
                        );
                    }, this)}
                </div>
            );
        }
    });

    controls.SelectAllCheckbox = React.createClass({
        render: function() {
            return this.transferPropsTo(<Input type='checkbox' label={$.t('common.select_all')} commonClassName='select-all' />);
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
        render: function() {
            var tableClasses = {'table table-bordered table-striped': true};
            tableClasses[this.props.tableClassName] = this.props.tableClassName;
            return (
                <table className={cx(tableClasses)}>
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
