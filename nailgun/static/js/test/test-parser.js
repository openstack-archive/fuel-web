define(['chai', 'jquery', 'underscore', 'utils', 'models', 'expression_parser'],
    function (chai, $, _, utils, models, ExpressionParser) {
        var expect = chai.expect;
        var should = chai.should();

        describe('just checking', function () {

            it('chai should work', function () {
                expect('a').to.equal('a');
            });

            it('works for jquery', function () {
                var el = $('<div>require.js up and running</div>');
                expect(el.text()).to.equal('require.js up and running');
            });

            it('works for underscore', function () {
                // just checking that _ works
                expect(_.size([1, 2, 3])).to.equal(3);
            });
        });

        describe('utils checking', function () {
            ExpressionParser.yy = {
                _: _,
                utils: utils,
                models: models || {},
                modelPaths: {}
            };

            var testModels = {
                'cluster': new models.Cluster(),
                'settings': new models.Settings()
            };

            it('should parse expressions', function () {
                var testCases = [
                    {'true': true},
                    {'false': false},
                    {'123': 123},
                    {'"123"': '123'},
                    {"'123'": '123'},
                    //test null
                    {'null': null},
                    {'null == false': false},
                    {'null == true': false},
                    {'null == null': true},
                    //test boolean operators
                    {'true or false': true},
                    {'true and false': false},
                    {'not true': false},
                    //test precedence
                    {'true or true and false or false': true},
                    {'true == true and false == false': true},
                    //test comparison
                    {'123 == 123': true},
                    {'123 == 321': false},
                    {'123 != 321': true},
                    {'123 != "123"': false},
                    //test grouping
                    {'(true or true) and not (false or false)': true},
                    //test errors
                    {'(true': new Error()},
                    {'false and': new Error()},
                    {'== 123': new Error()},
                    {'#^@$*()#@!': new Error()}

                ];
                _.each(testCases, function (testCase) {
                    if (_.values(testCase)[0] instanceof Error) {
                        (function() {utils.evaluateExpression(_.keys(testCase)[0], testModels);}).should.throw(Error);
                    }
                    else {
                        var evali;
                        evali = utils.evaluateExpression(_.keys(testCase)[0], testModels);
                        expect(evali.value).to.equal(_.values(testCase)[0]);
                    }
                });
            });

            it('should work correctly with modelpaths', function() {
                var hypervisor = 'qemu';
                var filledTestModels = {
                    'cluster': new models.Cluster({
                        mode: 'ha_compact'
                    }),
                    'settings': new models.Settings({
                        common: {
                            libvirt_type: {
                                value: 'qemu'
                            }
                        }
                    }),
                    'release': new models.Release({
                        roles: ['controller', 'compute']
                    })
                };

                 var testCases = [
                    {'cluster:mode': 'ha_compact'},
                    {'cluster:mode == "ha_compact"': true},
                    {'cluster:mode != "multinode"': true},
                    {'"controller" in release:roles': true},
                    {'"unknown-role" in release:roles': false},
                    {'settings:common.libvirt_type.value': hypervisor},
                    {'settings:common.libvirt_type.value == "qemu"': true},
                    {'cluster:mode == "ha_compact" and not (settings:common.libvirt_type.value != "qemu")': true}
                ];

                _.each(testCases, function (testCase) {
                    var evali;
                    evali = utils.evaluateExpression(_.keys(testCase)[0], filledTestModels);
                    expect(evali.value).to.equal(_.values(testCase)[0]);
                });
            });


        });

    });
