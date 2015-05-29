/*
Code used for displaying in game recipes from a json file

- Author: Adam Dybczak (RaTilicus)
*/
var recipe_tpl = _.template($('script.recipe_template').html());
var recipe_grid_tpl = _.template($('script.recipe_grid_template').html());

function onClickRecipe(event, t) {
    /* display a recipe 
    there are 2 types of recipes
    - craftgrid type (require placement of items in exact locations in the 5x5 grid)
    - other (just requires the right ingredient, not exact place, might not even have a grid)
    */
    var el = $(event.target),
        i = el.attr('i');
    if (el.hasClass('selected')) {
        console.log('already selected');
        return
    }
    $('#recipes div.selected').toggleClass('selected', false)
    el.toggleClass('selected', true)

    var recipe = window.recipes[i]
    console.log('selected', i, recipe);
    if (recipe.grid) {
        var data = recipe_grid_tpl({recipe: recipe});
    } else {
        var data = recipe_tpl({recipe: recipe});
    }

    $('#recipe').html(data);
}

$.get('/static/recipes.json', function(data) {
    /* load recipes file */
    window.recipes = data;
    var rdiv = $('#recipes')
    for(r in data) {
        var recipe = data[r],
            grid = {};
        for(i in recipe.ingredients) {
            var ingredient = recipe.ingredients[i];
            if (ingredient.grid) {
                grid[ingredient.grid] = ingredient.title+' x'+ingredient.count;
            }
            if (! _.isEmpty(grid)) {
                recipe.grid = grid;
            }
        }
        rdiv.append($('<div i="'+r+'">'+recipe.title+'</div>'))
    }
    rdiv.find('div').css({cursor:'pointer'}).on('click', onClickRecipe)
})

