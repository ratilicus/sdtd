from xml.dom import minidom
import simplejson as json
import re

'''
items.xml
    items
        item(id, name)
            property(name,value)
            property(class)
                property(name, value)

loot.xml
    lootcontainers
        lootplaceholders
            placeholder(name)
                block(name, prob)

        lootgroup(name)
            item(name, count, [prob])
            item(group, [prob])

        lootcontainer(id, count, size, sound_open, sound_close)
            item(name, count, [prob])
            item(group, [prob])

entityclasses.xml
    entity_classes
        entity_class(name, [extends])
            property(name, value, [param1, [param2]])

materials.xml
    materials
        material(id)
            property(name, value, [type])

groups.xml
    groups
        group(name, color, alpha)

blocks.xml
    blocks
        block(id, name)
            property(name, value, [param1, [param2]])
            property(class)
                property(name, value, [param1, [param2]])

            drop(eventm name, count, prob)

'''

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
           for recipe in get_recipes(xml=minidom.parse('Config/recipes.xml'))]
recipes.sort(key=lambda r: r['name'])
with open('static/recipes.json', 'w') as of:
    of.write(json.dumps(recipes))

