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

/*
 * Copyright (с) 2014 Stephen J. Collings, Matthew Honnibal, Pieter Vanderwerff
 *
 * Based on https://github.com/react-bootstrap/react-bootstrap/blob/master/src/Input.jsx
**/

define(['jquery', 'underscore', 'react'], function($, _, React) {
    'use strict';

    var controls = {},
        cx = React.addons.classSet;

    var tooltipMixin = {
        componentDidMount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip();
        },
        componentDidUpdate: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip();
        },
        componentWillUnmount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip('destroy');
        },
        renderTooltipIcon: function() {
            return this.props.tooltipText ? (
                <i key='tooltip' ref='tooltip' className='icon-attention text-warning' data-toggle='tooltip' title={this.props.tooltipText} />
            ) : null;
        }
    };

    controls.Input = React.createClass({
        mixins: [tooltipMixin],
        propTypes: {
            type: React.PropTypes.string.isRequired,
            name: React.PropTypes.string,
            label: React.PropTypes.renderable,
            description: React.PropTypes.renderable,
            disabled: React.PropTypes.bool,
            wrapperClassName: React.PropTypes.renderable,
            labelClassName: React.PropTypes.renderable,
            descriptionClassName: React.PropTypes.renderable,
            tooltipText: React.PropTypes.renderable,
            toggleable: React.PropTypes.bool
        },
        getInitialState: function() {
            return {visible: false};
        },
        togglePassword: function() {
            if (this.props.disabled) return;
            this.setState({visible: !this.state.visible});
        },
        isCheckboxOrRadio: function() {
            return this.props.type == 'radio' || this.props.type == 'checkbox';
        },
        onChange: function() {
            var input = this.refs.input.getDOMNode();
            return this.props.onChange(this.props.name, this.props.type == 'checkbox' ? input.checked : input.value);
        },
        renderInput: function() {
            var input = null,
                className = 'parameter-input';
            switch (this.props.type) {
                case 'select':
                    input = (<select ref='input' key='input' className={className} onChange={this.onChange}>{this.props.children}</select>);
                    break;
                case 'textarea':
                    input = <textarea ref='input' key='input' className={className} onChange={this.onChange} />;
                    break;
                case 'password':
                    var type = (this.props.toggleable && this.state.visible) ? 'text' : 'password';
                    input = <input ref='input' key='input' className={className} type={type} onChange={this.onChange} />;
                    break;
                default:
                    input = <input ref='input' key='input' className={className} onChange={this.onChange} value={this.props.value} />;
            }
            return this.isCheckboxOrRadio() ? (
                <div key='input-wrapper' className='custom-tumbler'>
                    {this.transferPropsTo(input)}
                    <span>&nbsp;</span>
                </div>
            ) : this.transferPropsTo(input);
        },
        renderToggleablePasswordAddon: function() {
            return this.props.toggleable ? (
                <span key='add-on' className='add-on' onClick={this.togglePassword}>
                    <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                </span>
            ) : null;
        },
        renderLabel: function(children) {
            var classes = {
                'parameter-name enable-selection': true,
                'input-append': this.props.toggleable
            };
            classes[this.props.labelClassName] = this.props.labelClassName;
            var labelWrapperClasses = {
                'label-wrapper': true
            };
            labelWrapperClasses[this.props.labelWrapperClassName] = this.props.labelWrapperClassName;
            return this.props.label ? (
                <label key='label' className={cx(classes)} htmlFor={this.props.id}>
                    {!this.isCheckboxOrRadio() &&
                        <div className='input-label'>
                            <span>{this.props.label}</span>
                            {this.renderTooltipIcon()}
                        </div>
                    }
                    {children}
                    {this.isCheckboxOrRadio() &&
                        <div className={cx(labelWrapperClasses)}>
                            {this.props.label}
                            {this.renderTooltipIcon()}
                        </div>
                    }
                </label>
            )
            : this.props.title ? (
                <div key={this.props.title}>
                    <div className='parameter-name'>{this.props.title}</div>
                    {children}
                </div>
                )
            : children;
        },
        renderDescription: function() {
            var error = !_.isUndefined(this.props.error) && !_.isNull(this.props.error),
                classes = {'parameter-description enable-selection': true};
            classes[this.props.descriptionClassName] = this.props.descriptionClassName;
            return error || this.props.description ? (
                <div key='description' className={cx(classes)}>
                    {error ? this.props.error : this.props.description}
                </div>
            ) : null;
        },
        renderWrapper: function(children) {
            var classes = {
                'parameter-box': true,
                clearfix: !this.isCheckboxOrRadio(),
                'has-error': !_.isUndefined(this.props.error) && !_.isNull(this.props.error)
            };
            classes[this.props.wrapperClassName] = this.props.wrapperClassName;
            return (<div className={cx(classes)}>{children}</div>);
        },
        render: function() {
            return this.renderWrapper([
                this.renderLabel([
                    this.renderInput(),
                    this.renderToggleablePasswordAddon()
                ]),
                this.renderDescription()
            ]);
        }
    });

    controls.RadioGroup = React.createClass({
        mixins: [tooltipMixin],
        propTypes: {
            name: React.PropTypes.string,
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            label: React.PropTypes.renderable,
            labelClassName: React.PropTypes.renderable,
            tooltipText: React.PropTypes.renderable
        },
        render: function() {
            var labelClasses = {'parameter-name': true};
            labelClasses[this.props.labelClassName] = this.props.labelClassName;
            return (
                <div className='radio-group'>
                    {this.props.label &&
                        <label className={cx(labelClasses)}>
                            {this.props.label}
                            {this.renderTooltipIcon()}
                        </label>
                    }
                    {_.map(this.props.values, function(value) {
                        return this.transferPropsTo(
                            <controls.Input
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
        propTypes: {
            tableClassName: React.PropTypes.string,
            head: React.PropTypes.array,
            body: React.PropTypes.array
        },
        render: function() {
            var tableClasses = {'table table-bordered table-striped': true};
            tableClasses[this.props.tableClassName] = this.props.tableClassName;
            return (
                <table className={cx(tableClasses)}>
                    <thead>
                        <tr>
                            {_.map(this.props.head, function(column, index) {
                                var classes = {};
                                classes[column.className] = column.className;
                                return <th key={index} className={cx(classes)}>{column.label}</th>;
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

    controls.Range = React.createClass({
        propTypes: {
            wrapperClassName: React.PropTypes.renderable,
            type: React.PropTypes.oneOf(['normal', 'mini']),
            attribute: React.PropTypes.string,
            networkAttribute: React.PropTypes.array
        },
        autoCompleteRange: function(error, rangeStart, event) {
            var input = event.target;
            if (_.isUndefined(error)) {
                input.value = rangeStart;
            }
            if (input.setSelectionRange) {
                var startPos = _.lastIndexOf(rangeStart, '.') + 1;
                var endPos = rangeStart.length;
                _.defer(function() { input.setSelectionRange(startPos, endPos); });
            }
        },
        render: function() {
            var wrapperClasses = {},
                rowHeaderClasses = {
                    'range-row-header': true,
                    mini: this.props.type == 'mini'
                },
                inputClassName = {
                    range: true,
                    mini: this.props.type == 'mini'
                },
                startErrorMessage = '',
                endErrorMessage = '',
                errorIndexMatch;
            wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;
            if (this.props.error) {
                startErrorMessage = this.props.error[0];
                endErrorMessage = this.props.error[1];
                errorIndexMatch = true;
            }
            return (
                <div className={cx(wrapperClasses)}>
                    {!this.props.noLabel &&
                        <div className={cx(rowHeaderClasses)}>
                            <div>{$.t('cluster_page.network_tab.range_start')}</div>
                            <div>{$.t('cluster_page.network_tab.range_end')}</div>
                        </div>
                    }
                    <div className='parameter-name'>{this.props.nameLabel}</div>
                    { (this.props.type == 'normal') ?
                        <div className={this.props.rowsClassName}>
                            {_.map(this.props.networkAttribute, function(range, index) {
                                if (this.props.error) {
                                    if (_.isPlainObject(this.props.error[0])) {
                                        startErrorMessage =  _.pluck(this.props.error, 'start')[0];
                                        endErrorMessage = _.pluck(this.props.error, 'end')[0];
                                        errorIndexMatch =  _.pluck(this.props.error, 'index')[0] == index;
                                    }
                                }
                                return (
                                    <div className='range-row autocomplete clearfix' key={index}>
                                        <label className='parameter-box clearfix'>
                                            <div className='parameter-control'>
                                                {this.transferPropsTo(
                                                    <input className={cx(_.extend(inputClassName, {error: !!startErrorMessage && errorIndexMatch}))}
                                                        type='text' name='range0' placeholder='127.0.0.1' value={range[0]}
                                                    />
                                                )}
                                            </div>
                                        </label>
                                        <label className='parameter-box clearfix'>
                                            <div className='parameter-control'>
                                                {this.transferPropsTo(
                                                    <input className={cx(_.extend(inputClassName, {error: !!endErrorMessage && errorIndexMatch}))}
                                                        type='text' name='range1' placeholder='127.0.0.1' value={range[1]}
                                                        onFocus={this.autoCompleteRange.bind(this, startErrorMessage, range[0])}
                                                    />
                                                )}
                                            </div>
                                        </label>
                                        {!this.props.noControls &&
                                            <div>
                                                <div className='ip-ranges-control'>
                                                    <button className='btn btn-link ip-ranges-add' disabled={this.props.disabled} onClick={this.props.addRange}>
                                                        <i className='icon-plus-circle'></i>
                                                    </button>
                                                </div>
                                                {(this.props.networkAttribute.length > 1) &&
                                                    <div className='ip-ranges-control'>
                                                        <button className='btn btn-link ip-ranges-delete' disabled={this.props.disabled} onClick={this.props.removeRange}>
                                                            <i className='icon-minus-circle'></i>
                                                        </button>
                                                    </div>
                                                }
                                            </div>
                                        }
                                        <div className='error validation-error'>
                                            <span className='help-inline'>{errorIndexMatch ? (startErrorMessage || endErrorMessage) : '' }</span>
                                        </div>
                                    </div>
                                );
                            }, this)}
                        </div>
                    :
                        <div className='range-row'>
                            <div className='parameter-control'>
                                {this.transferPropsTo(<input type='text' className={cx(_.extend(inputClassName, {error: !!startErrorMessage}))}
                                name='range0' value={this.props.networkAttribute[0]} />)}
                            </div>
                            <div className='parameter-control'>
                                {this.transferPropsTo(<input type='text' className={cx(_.extend(inputClassName, {error: !!endErrorMessage}))}
                                    name='range1' value={this.props.networkAttribute[1]} disabled={this.props.disableEnd || this.props.disabled}/>)}
                            </div>
                            <div className='error validation-error'>
                                <span className='help-inline'>{startErrorMessage || endErrorMessage}</span>
                            </div>
                        </div>
                    }
                </div>
            );
        }
    });

    controls.checkboxAndInput = React.createClass({
        render: function() {
            return (
                <div className='network-attribute complex-control vlan-tagging'>
                    {this.transferPropsTo(
                        <controls.Input
                            onChange={this.props.onCheckboxChange}
                            type='checkbox'
                            checked={!_.isNull(this.props.value)}
                        />
                    )}
                    {(this.props.enabled) ?
                        <div>
                            {this.transferPropsTo(
                                <controls.Input
                                    title=''
                                    onChange={this.props.onInputChange}
                                    type ='text'
                                    error={this.props.inputError}
                                />
                            )}
                        </div>
                    :
                        <div></div>
                    }

                </div>
            );
        }
    });

    return controls;
});
