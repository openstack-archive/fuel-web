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
define(['jquery', 'underscore', 'react'], function($, _, React) {
    'use strict';

    var controls = {},
        cx = React.addons.classSet;

    var tooltipMixin = {
        componentDidMount: function() {
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
            // props used by <input />
            type: React.PropTypes.string.isRequired,
            name: React.PropTypes.string,
            defaultValue: React.PropTypes.oneOfType([
                React.PropTypes.string,
                React.PropTypes.number,
                React.PropTypes.bool
            ]),
            defaultChecked: React.PropTypes.bool,
            disabled: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            onKeyDown: React.PropTypes.func,
            maxLength: React.PropTypes.renderable,
            // other props
            label: React.PropTypes.renderable,
            description: React.PropTypes.renderable,
            commonClassName: React.PropTypes.renderable,
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
            return this.props.type === 'radio' || this.props.type === 'checkbox';
        },
        onChange: function() {
            var input = this.refs.input.getDOMNode();
            return this.props.onChange(this.props.name, this.props.type === 'checkbox' ? input.checked : input.value);
        },
        renderInput: function() {
            var input = null,
                className = 'parameter-input';
            switch (this.props.type) {
                case 'dropdown':
                    input = (<select ref='input' key='input' className={className} onChange={this.onChange}>{this.props.children}</select>);
                    break;
                case 'textarea':
                    input = <textarea ref='input' key='input' className={className} onChange={this.onChange} />;
                    break;
                default:
                    input = <input ref='input' key='input' className={className} onChange={this.onChange} />;
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
            return this.props.label ? (
                <label key='label' className={cx(classes)} htmlFor={this.props.id}>
                    {children}
                    <div className='label-wrapper'>
                        {this.props.label}
                        {this.renderTooltipIcon()}
                    </div>
                </label>
            ) : children;
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
                'has-error': !_.isUndefined(this.props.error) && !_.isNull(this.props.error)
            };
            classes[this.props.commonClassName] = this.props.commonClassName;
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

    controls.SelectAllCheckbox = React.createClass({
        render: function() {
            return this.transferPropsTo(<controls.Input type='checkbox' label={$.t('common.select_all')} commonClassName='select-all' />);
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
