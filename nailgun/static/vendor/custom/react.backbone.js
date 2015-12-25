/*
 *  Taken from https://github.com/clayallsopp/react.backbone
 *  Modified for better debouncing of collection events
 *
 *  The MIT License (MIT)
 *
 *  Copyright (c) 2013 Turboprop Inc
 *
 *  Permission is hereby granted, free of charge, to any person obtaining a copy of
 *  this software and associated documentation files (the "Software"), to deal in
 *  the Software without restriction, including without limitation the rights to
 *  use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 *  the Software, and to permit persons to whom the Software is furnished to do so,
 *  subject to the following conditions:
 *
 *  The above copyright notice and this permission notice shall be included in all
 *  copies or substantial portions of the Software.
 *
 *  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 *  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 *  FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 *  COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 *  IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 *  CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
**/

(function(root, factory) {
    if (typeof exports === 'object') {
        // CommonJS
        module.exports = factory(require('backbone'), require('react'), require('underscore'));
    } else if (typeof define === 'function' && define.amd) {
        // AMD. Register as an anonymous module.
        define(['backbone', 'react', 'underscore'], factory);
    } else {
        // Browser globals
        root.amdWeb = factory(root.Backbone, root.React, root._);
    }
}(this, function(Backbone, React, _) {

    'use strict';

    var collectionBehavior = {
        changeOptions: 'update reset sort',
        updateScheduler: function(func) { return _.debounce(func, 0, {leading: true, trailing: true}); }
    };

    var modelBehavior = {
        changeOptions: 'change',
        //note: if we debounce models too we can no longer use model attributes
        //as properties to react controlled components due to https://github.com/facebook/react/issues/955
        updateScheduler: _.identity
    };

    var subscribe = function(component, modelOrCollection, customChangeOptions) {
        if (!modelOrCollection) {
            return;
        }

        var behavior = modelOrCollection instanceof Backbone.Collection ? collectionBehavior : modelBehavior;

        var triggerUpdate = behavior.updateScheduler(function() {
            if (component.isMounted()) {
                (component.onModelChange || component.forceUpdate).call(component);
            }
        });

        var changeOptions = customChangeOptions || component.changeOptions || behavior.changeOptions;
        modelOrCollection.on(changeOptions, triggerUpdate, component);
    };

    var unsubscribe = function(component, modelOrCollection) {
        if (!modelOrCollection) {
            return;
        }

        modelOrCollection.off(null, null, component);
    };

    React.BackboneMixin = function(optionsOrPropName, customChangeOptions) {
      var propName, modelOrCollection;
      if (typeof optionsOrPropName === "object") {
          customChangeOptions = optionsOrPropName.renderOn;
          propName = optionsOrPropName.propName;
          modelOrCollection = optionsOrPropName.modelOrCollection;
      } else {
          propName = optionsOrPropName;
      }

      if (!modelOrCollection) {
          modelOrCollection = function(props) {
            return props[propName];
          }
      }

      return {
        componentDidMount: function() {
            // Whenever there may be a change in the Backbone data, trigger a reconcile.
            subscribe(this, modelOrCollection(this.props), customChangeOptions);
        },

        componentWillReceiveProps: function(nextProps) {
            if (modelOrCollection(this.props) === modelOrCollection(nextProps)) {
                return;
            }

            unsubscribe(this, modelOrCollection(this.props));
            subscribe(this, modelOrCollection(nextProps), customChangeOptions);

            if (typeof this.componentWillChangeModel === 'function') {
                this.componentWillChangeModel();
            }
        },

        componentDidUpdate: function(prevProps, prevState) {
            if (modelOrCollection(this.props) === modelOrCollection(prevProps)) {
                return;
            }

            if (typeof this.componentDidChangeModel === 'function') {
                this.componentDidChangeModel();
            }
        },

        componentWillUnmount: function() {
            // Ensure that we clean up any dangling references when the component is destroyed.
            unsubscribe(this, modelOrCollection(this.props));
        }
      };
    };

    React.BackboneViewMixin = {
        getModel: function() {
            return this.props.model;
        },

        model: function() {
            return this.getModel();
        },

        getCollection: function() {
            return this.props.collection;
        },

        collection: function() {
            return this.getCollection();
        },

        el: function() {
            return this.isMounted() && ReactDOM.findDOMNode(this);
        }
    };

    React.createBackboneClass = function(spec) {
        var currentMixins = spec.mixins || [];

        spec.mixins = currentMixins.concat([
            React.BackboneMixin('model'),
            React.BackboneMixin('collection'),
            React.BackboneViewMixin
        ]);

        return React.createClass(spec);
    };

    return React;
}));
