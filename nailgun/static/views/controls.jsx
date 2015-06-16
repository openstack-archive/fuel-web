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

define(['i18n', 'jquery', 'underscore', 'react', 'utils', 'jsx!component_mixins'],
    function(i18n, $, _, React, utils, componentMixins) {
    'use strict';

    var controls = {};

    var tooltipMixin = controls.tooltipMixin = {
        componentDidMount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip();
        },
        componentDidUpdate: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip('destroy').tooltip();
        },
        componentWillUnmount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip('destroy');
        },
        renderTooltipIcon: function() {
            return this.props.tooltipText ? (
                <i
                    key='tooltip'
                    ref='tooltip'
                    className='glyphicon glyphicon-warning-sign tooltip-icon'
                    data-toggle='tooltip'
                    data-placement='right'
                    title={this.props.tooltipText}
                />
            ) : null;
        }
    };

    controls.Input = React.createClass({
        mixins: [tooltipMixin],
        propTypes: {
            type: React.PropTypes.oneOf(['text', 'password', 'textarea', 'checkbox', 'radio', 'select', 'hidden', 'number', 'range', 'file']).isRequired,
            name: React.PropTypes.node,
            label: React.PropTypes.node,
            description: React.PropTypes.node,
            disabled: React.PropTypes.bool,
            inputClassName: React.PropTypes.node,
            wrapperClassName: React.PropTypes.node,
            tooltipText: React.PropTypes.node,
            toggleable: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            onInput: React.PropTypes.func,
            extraContent: React.PropTypes.node
        },
        getInitialState: function() {
            return {
                visible: false,
                fileName: this.props.defaultValue && this.props.defaultValue.name || null,
                content: this.props.defaultValue && this.props.defaultValue.content || null
            };
        },
        togglePassword: function() {
            this.setState({visible: !this.state.visible});
        },
        isCheckboxOrRadio: function() {
            return this.props.type == 'radio' || this.props.type == 'checkbox';
        },
        getInputDOMNode: function() {
            return this.refs.input.getDOMNode();
        },
        debouncedChange: _.debounce(function() {
            return this.onChange();
        }, 200, {leading: true}),
        debouncedInput: _.debounce(function() {
            return this.onInput();
        }, 10, {leading: true}),
        pickFile: function() {
            this.getInputDOMNode().click();
        },
        saveFile: function(fileName, content) {
            this.setState({
                fileName: fileName,
                content: content
            });
            return this.props.onChange(
                this.props.name,
                {name: fileName, content: content}
            );
        },
        removeFile: function() {
            this.refs.form.getDOMNode().reset();
            this.saveFile(null, null);
        },
        readFile: function() {
            var reader = new FileReader(),
                input = this.getInputDOMNode();

            if (input.files.length) {
                reader.onload = (function() {
                    return this.saveFile(input.value.replace(/^.*[\\\/]/g, ''), reader.result);
                }).bind(this);
                reader.readAsBinaryString(input.files[0]);
            }
        },
        onChange: function() {
            if (this.props.onChange) {
                var input = this.getInputDOMNode();
                return this.props.onChange(
                    this.props.name,
                    this.props.type == 'checkbox' ? input.checked : input.value
                );
            }
        },
        onInput: function() {
            if (this.props.onInput) {
                var input = this.getInputDOMNode();
                return this.props.onInput(this.props.name, input.value);
            }
        },
        renderInput: function() {
            var classes = {'form-control': this.props.type != 'range'};
            classes[this.props.inputClassName] = this.props.inputClassName;
            var props = {
                    ref: 'input',
                    key: 'input',
                    type: (this.props.toggleable && this.state.visible) ? 'text' : this.props.type,
                    className: utils.classNames(classes)
                };
            if (this.props.type == 'range') {
                props.onInput = this.debouncedInput;
            } else if (this.props.type == 'file') {
                props.onChange = this.readFile;
            } else {
                // debounced onChange callback is supported for uncontrolled inputs
                props.onChange = (_.isUndefined(this.props.value) && _.isUndefined(this.props.checked)) ? this.debouncedChange : this.onChange;
            }
            var Tag = _.contains(['select', 'textarea'], this.props.type) ? this.props.type : 'input',
                input = <Tag {...this.props} {...props}>{this.props.children}</Tag>,
                isCheckboxOrRadio = this.isCheckboxOrRadio(),
                inputWrapperClasses = {
                    'input-group': this.props.toggleable,
                    'custom-tumbler': isCheckboxOrRadio,
                    textarea: this.props.type == 'textarea'
                };
            if (this.props.type == 'file') {
                input = <form ref='form'>{input}</form>;
            }
            return (
                <div key='input-group' className={utils.classNames(inputWrapperClasses)}>
                    {input}
                    {this.props.type == 'file' &&
                        <div className='input-group'>
                            <input
                                className='form-control file-name'
                                type='text'
                                placeholder={i18n('controls.file.placeholder')}
                                value={this.state.fileName && '[' + utils.showSize(this.state.content.length) + '] ' + this.state.fileName}
                                onClick={this.pickFile}
                                readOnly />
                                <div className='input-group-addon' onClick={this.state.fileName ? this.removeFile : this.pickFile}>
                                    <i className={this.state.fileName ? 'glyphicon glyphicon-remove' : 'glyphicon glyphicon-file'} />
                                </div>
                        </div>
                    }
                    {this.props.toggleable &&
                        <div className='input-group-addon' onClick={this.togglePassword}>
                            <i className={this.state.visible ? 'glyphicon glyphicon-eye-close' : 'glyphicon glyphicon-eye-open'} />
                        </div>
                    }
                    {isCheckboxOrRadio && <span>&nbsp;</span>}
                    {this.props.extraContent}
                </div>
            );
        },
        renderLabel: function(children) {
            return (
                <label key='label' htmlFor={this.props.id}>
                    {children}
                    {this.props.label}
                    {this.renderTooltipIcon()}
                </label>
            );
        },
        renderDescription: function() {
            return (
                <span key='description' className='help-block'>
                    {!_.isUndefined(this.props.error) && !_.isNull(this.props.error) ?
                        this.props.error :
                        this.props.description && this.props.description.split('\n').map(function(line, index) {
                                return <p key={index}>{line}</p>;
                            }
                        )
                    }
                </span>
            );
        },
        renderWrapper: function(children) {
            var isCheckboxOrRadio = this.isCheckboxOrRadio(),
                classes = {
                    'form-group': !isCheckboxOrRadio,
                    'checkbox-group': isCheckboxOrRadio,
                    'has-error': !_.isUndefined(this.props.error) && !_.isNull(this.props.error),
                    disabled: this.props.disabled
                };
            classes[this.props.wrapperClassName] = this.props.wrapperClassName;
            return (<div className={utils.classNames(classes)}>{children}</div>);
        },
        render: function() {
            return this.renderWrapper(this.isCheckboxOrRadio() ?
                [
                    this.renderLabel(this.renderInput()),
                    this.renderDescription()
                ] : [
                    this.renderLabel(),
                    this.renderInput(),
                    this.renderDescription()
                ]
            );
        }
    });

    controls.RadioGroup = React.createClass({
        mixins: [tooltipMixin],
        propTypes: {
            name: React.PropTypes.string,
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            label: React.PropTypes.node,
            tooltipText: React.PropTypes.node
        },
        render: function() {
            return (
                <div className='radio-group'>
                    {this.props.label &&
                        <h4>
                            {this.props.label}
                            {this.renderTooltipIcon()}
                        </h4>
                    }
                    {_.map(this.props.values, function(value) {
                        return <controls.Input
                            {...this.props}
                            {...value}
                            type='radio'
                            key={value.data}
                            value={value.data}
                        />;
                    }, this)}
                </div>
            );
        }
    });

    controls.ProgressBar = React.createClass({
        render: function() {
            return (
                <div className='progress'>
                    <div className='progress-bar progress-bar-striped active' style={{width: '100%'}}></div>
                </div>
            );
        }
    });

    controls.Table = React.createClass({
        propTypes: {
            tableClassName: React.PropTypes.node,
            head: React.PropTypes.array,
            body: React.PropTypes.array
        },
        render: function() {
            var tableClasses = {'table table-bordered': true, 'table-striped': !this.props.noStripes};
            tableClasses[this.props.tableClassName] = this.props.tableClassName;
            return (
                <table className={utils.classNames(tableClasses)}>
                    <thead>
                        <tr>
                            {_.map(this.props.head, function(column, index) {
                                var classes = {};
                                classes[column.className] = column.className;
                                return <th key={index} className={utils.classNames(classes)}>{column.label}</th>;
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

    controls.Popover = React.createClass({
        mixins: [componentMixins.outerClickMixin],
        propTypes: {
            className: React.PropTypes.node,
            placement: React.PropTypes.node
        },
        getDefaultProps: function() {
            return {placement: 'bottom'};
        },
        render: function() {
            var classes = {'popover in': true};
            classes[this.props.placement] = true;
            classes[this.props.className] = true;
            return (
                <div className={utils.classNames(classes)}>
                    <div className='arrow' />
                    <div className='popover-content'>{this.props.children}</div>
                </div>
            );
        }
    });

    return controls;
});
