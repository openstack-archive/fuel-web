module.exports = {
    entry: './static/app.js',
    output: {
        path: __dirname + '/static/build/',
        publicPath: '/static/',
        filename: 'bundle.js',
        chunkFilename: null,
        sourceMapFilename: 'bundle.js.map'
    },
    module: {
        loaders: [
            {test: /\.css$/, loader: 'style!css'},
            {test: /\.less$/, loader: 'style!css!less'},
            {test: /\.html$/, loader: 'raw'},
            {test: /\.json$/, loader: 'json'},
            {test: /\.jsx$/, loader: 'babel-loader', exclude: /(node_modules|bower_components)/},
            {test: /\.(woff|woff2|ttf|eot|svg)(\?v=\d+\.\d+\.\d+)?$/, loader: 'file'},
            {test: /\.(gif|png)$/, loader: 'file'}
        ]
    },
    resolve: {
        modulesDirectories: ['static', 'node_modules', 'vendor/custom'],
        extensions: ['', '.js', '.jsx'],
        alias: {
            underscore: 'lodash',
            react: 'react/addons',
            routefilter: 'vendor/custom/backbone.routefilter.js',
            deepModel: 'vendor/custom/deep-model.js',
            //i18next: '../node_modules/i18next/lib/dep/i18next-1.7.1.js'
        }
    },
    node: {
        fs: 'empty'
    },
    devtool: '#source-map'
};
