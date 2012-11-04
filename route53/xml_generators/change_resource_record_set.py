from io import BytesIO
from lxml import etree
from route53.util import prettyprint_xml

def get_change_values(change):
    """
    In the case of deletions, we pull the change values for the XML request
    from the ResourceRecordSet._initial_vas dict, since we want the original
    values. For creations, we pull from the attributes on ResourceRecordSet.

    Since we're dealing with attributes vs. dict key/vals, we'll abstract
    this part away here and just always pass a dict to write_change.

    :rtype: dict
    :returns: A dict of change data, used by :py:func:`write_change` to
        write the change request XML.
    """

    action, rrset = change

    if action == 'CREATE':
        # For creations, we want the new values. They don't need to match.
        return dict(
            name=rrset.name,
            ttl=rrset.ttl,
            records=rrset.records,
        )
    else:
        # We can just dump the initial values dict for deletions, since we
        # want the original values to match in the deletion request.
        return rrset._initial_vals

def write_change(change):
    """
    Creates an XML element for the change.

    :param tuple change: A change tuple from a ChangeSet. Comes in the form
        of ``(action, rrset)``.
    :rtype: lxml.etree._Element
    :returns: A fully baked Change tag.
    """

    action, rrset = change

    change_vals = get_change_values(change)

    e_change = etree.Element("Change")

    e_action = etree.SubElement(e_change, "Action")
    e_action.text = action

    e_rrset = etree.SubElement(e_change, "ResourceRecordSet")

    e_name = etree.SubElement(e_rrset, "Name")
    e_name.text = change_vals['name']

    e_type = etree.SubElement(e_rrset, "Type")
    e_type.text = rrset.rrset_type

    e_ttl = etree.SubElement(e_rrset, "TTL")
    e_ttl.text = str(change_vals['ttl'])


    if rrset.is_alias_record_set():
        # A record sets in Alias mode don't have any resource records.
        return e_change

    e_resource_records = etree.SubElement(e_rrset, "ResourceRecords")

    for value in change_vals['records']:
        e_resource_record = etree.SubElement(e_resource_records, "ResourceRecord")
        e_value = etree.SubElement(e_resource_record, "Value")
        e_value.text = value

    return e_change

def change_resource_record_set_writer(connection, change_set, comment=None):
    """
    Forms an XML string that we'll send to Route53 in order to change
    record sets.

    :param Route53Connection connection: The connection instance used to
        query the API.
    :param change_set.ChangeSet change_set: The ChangeSet object to create the
        XML doc from.
    :keyword str comment: An optional comment to go along with the request.
    """

    e_root = etree.Element(
        "ChangeResourceRecordSetsRequest",
        xmlns=connection.xml_namespace
    )

    e_change_batch = etree.SubElement(e_root, "ChangeBatch")

    if comment:
        e_comment = etree.SubElement(e_change_batch, "Comment")
        e_comment.text = comment

    e_changes = etree.SubElement(e_change_batch, "Changes")

    # Deletions need to come first in the change sets.
    for change in change_set.deletions + change_set.creations:
        e_changes.append(write_change(change))

    e_tree = etree.ElementTree(element=e_root)

    print(prettyprint_xml(e_root))

    fobj = BytesIO()
    # This writes bytes.
    e_tree.write(fobj, xml_declaration=True, encoding='utf-8', method="xml")
    return fobj.getvalue().decode('utf-8')