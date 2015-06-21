from xml.dom import minidom
import simplejson as json
import re

camel_split = re.compile(r'(^[a-z]+|[A-Z][a-z]+|[a-z0-9]+)')

def get_items(xml):
    for obj_node in xml.getElementsByTagName('item'):
        obj = dict(obj_node.attributes.items())
        if 'name' in obj:
            obj['title'] = (' '.join(camel_split.findall(obj['name']))).title()
            print 'processing %s' % obj['name']
        else:
            raise Exception('Item has no name: %s' % obj)
        subs =[]
        for sub_node in obj_node.getElementsByTagName('ingredient'):
            sub = dict(sub_node.attributes.items())
            if 'class' in sub:
                subs2 = []
                for sub2_node in obj_node.getElementsByTagName('ingredient'):
                    sub2 = dict(sub2_node.attributes.items())
                    subs2.append(sub2)
                sub['properties'] = subs2
            subs.append(sub)
        obj['properties'] = subs
        yield obj

items = {item['name']: item for item in get_items(xml=minidom.parse('/home/sdtd/engine/Data/Config/items.xml'))}
#with open('/var/www/sdtd/static/recipes.json', 'w') as of:
#    of.write(json.dumps(recipes))

print items
