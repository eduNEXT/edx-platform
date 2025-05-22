(function(define) {
    define([
        'jquery',
        'underscore',
        'backbone',
        'gettext',
        'js/discovery/models/filter',
        'js/discovery/views/filter_label',
        'edx-ui-toolkit/js/utils/html-utils'
    ], function($, _, Backbone, gettext, Filter, FilterLabel, HtmlUtils) {
        'use strict';

        return Backbone.View.extend({

            el: '#filter-bar',
            templateId: '#filter_bar-tpl',

            events: {
                'click #clear-all-filters': 'clearAll',
                'click li .discovery-button': 'clearFilter'
            },

            initialize: function() {
                this.tpl = HtmlUtils.template($(this.templateId).html());
                this.render();
                this.listenTo(this.collection, 'remove', this.hideIfEmpty);
                this.listenTo(this.collection, 'add', this.addFilter);
                this.listenTo(this.collection, 'reset', this.resetFilters);

                // The following lines allows us to apply filters in the course page based on a URL.
                this.addFilterByURL();
                this.on('filter:updated', this.updateCourseDiscovery);
            },

            updateCourseDiscovery: function(filter) {
                var courseDiscovery = new CourseDiscovery();
                var filters = this.collection.map(function(model) {
                    return {
                        type: model.get('type'),
                        query: model.get('query')
                    };
                });

                if (filters.length === 0) return;

                const payload = { filters };

                courseDiscovery.fetch({
                    data: JSON.stringify(payload),
                    contentType: "application/json",
                    type: "POST"
                });
            },

            addFilterByURL: function() {
                // Parse filter params from URL and add to collection if present
                // Example URL: <domain>/courses?filtertype=org&filterquery=uah
                const urlParams = new URLSearchParams(window.location.search);
                const filterType = urlParams.get('filtertype');
                const filterQuery = urlParams.get('filterquery');

                if (!(filterType && filterQuery)) {
                    return;
                }

                const existingFilter = this.collection.get(filterType);
                if (existingFilter) {
                    this.trigger('clearFilter', filterType);
                }

                const filter = new Filter({
                    type: filterType,
                    query: filterQuery,
                    name: filterQuery
                });
                this.collection.add(filter);
                this.trigger('filter:updated', filter);
            },

            render: function() {
                HtmlUtils.setHtml(
                    this.$el,
                    this.tpl()
                );
                this.$ul = this.$el.find('ul');
                this.$el.addClass('is-animated');
                return this;
            },

            addFilter: function(filter) {
                var label = new FilterLabel({model: filter});
                this.$ul.append(label.render().el);
                this.show();
            },

            hideIfEmpty: function() {
                if (this.collection.isEmpty()) {
                    this.hide();
                }
            },

            resetFilters: function() {
                this.$ul.empty();
                this.hide();
            },

            clearFilter: function(event) {
                var $target = $(event.currentTarget);
                var filter = this.collection.get($target.data('type'));
                this.trigger('clearFilter', filter.id);
            },

            clearAll: function(event) {
                this.trigger('clearAll');
            },

            show: function() {
                this.$el.removeClass('is-collapsed');
            },

            hide: function() {
                this.$ul.empty();
                this.$el.addClass('is-collapsed');
            }

        });
    });
}(define || RequireJS.define));
