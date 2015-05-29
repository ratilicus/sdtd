from xml.dom import minidom
import simplejson as json
import re

camel_split = re.compile(r'(^[a-z]+|[A-Z][a-z]+|[a-z0-9]+)')

def get_recipes(xml):
    for recipe_node in xml.getElementsByTagName('recipe'):
        recipe = dict(recipe_node.attributes.items())
        recipe['title'] = (' '.join(camel_split.findall(recipe['name']))).title()
        recipe['ingredients'] = []
        for ingredient_node in recipe_node.getElementsByTagName('ingredient'):
            ingredient = dict(ingredient_node.attributes.items())
            ingredient['title'] = (' '.join(camel_split.findall(ingredient['name']))).title()
            recipe['ingredients'].append(ingredient)
        yield recipe

recipes = [recipe
           for recipe in get_recipes(xml=minidom.parse('/home/sdtd/engine/Data/Config/recipes.xml'))]
recipes.sort(key=lambda r: r['name'])
with open('/var/www/sdtd/static/recipes.json', 'w') as of:
    of.write(json.dumps(recipes))

