module.exports = {
    "Test cluster creation": function(browser) {
        browser
            .url('http://localhost:8000/#clusters')
            .waitForElementVisible('.login-box', 30000)
            .setValue('input[type=text]', 'admin')
            .setValue('input[type=password]', 'admin')
            .click('.login-btn')
            .waitForElementVisible('.cluster-list', 30000)
            .click('.create-cluster')
            .waitForElementVisible('.modal', 5000, 'Cluster creation dialog opens')
            .waitForElementVisible('.modal form select[name=release] option', 1000,
                'Release select box updates with releases')
            .setValue('form.create-cluster-form input[type=text]', 'name');
        for (var i = 0; i < 6; i++) {
            browser.click('.next-pane-btn');
        }
        browser
            .click('.finish-btn')
            .waitForElementVisible('.modal', 5000, 'Cluster creation dialog closes after from submission');
            .waitForElementPresent('.cluster-list a.clusterbox', 5000, 'Created cluster appears in list');
            .end();
    }
};

