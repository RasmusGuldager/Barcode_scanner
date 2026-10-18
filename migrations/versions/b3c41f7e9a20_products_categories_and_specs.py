"""products, categories and specs

Items with the same name (ignoring upper/lower case) become copies of one
product. The product takes over their category, description and size, which
were the same for every copy.

Revision ID: b3c41f7e9a20
Revises: a84d932de66e
Create Date: 2026-10-18 23:10:00

"""
from alembic import op
import sqlalchemy as sa

import app.extensions


# revision identifiers, used by Alembic.
revision = 'b3c41f7e9a20'
down_revision = 'a84d932de66e'
branch_labels = None
depends_on = None

MOVED = ["category", "description", "length_mm", "width_mm", "height_mm"]


def upgrade():
    op.create_table('category',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_category')),
    sa.UniqueConstraint('name', name=op.f('uq_category_name'))
    )
    op.create_table('product',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('length_mm', sa.Integer(), nullable=True),
    sa.Column('width_mm', sa.Integer(), nullable=True),
    sa.Column('height_mm', sa.Integer(), nullable=True),
    sa.Column('created_at', app.extensions.UTCDateTime(), nullable=False),
    sa.Column('updated_at', app.extensions.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], name=op.f('fk_product_category_id_category'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product')),
    sa.UniqueConstraint('name', name=op.f('uq_product_name'))
    )
    op.create_table('spec_field',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], name=op.f('fk_spec_field_category_id_category'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_spec_field')),
    sa.UniqueConstraint('category_id', 'name', name=op.f('uq_spec_field_category_id_name'))
    )
    op.create_table('spec_option',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['field_id'], ['spec_field.id'], name=op.f('fk_spec_option_field_id_spec_field'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_spec_option')),
    sa.UniqueConstraint('field_id', 'label', name=op.f('uq_spec_option_field_id_label'))
    )
    op.create_table('spec_value',
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('field_id', sa.Integer(), nullable=False),
    sa.Column('option_id', sa.Integer(), nullable=True),
    sa.Column('number', sa.Double(), nullable=True),
    sa.Column('text', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['field_id'], ['spec_field.id'], name=op.f('fk_spec_value_field_id_spec_field'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['option_id'], ['spec_option.id'], name=op.f('fk_spec_value_option_id_spec_option'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_spec_value_product_id_product'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('product_id', 'field_id', name=op.f('pk_spec_value'))
    )

    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))

    _items_to_products()

    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.alter_column('product_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(batch_op.f('fk_item_product_id_product'), 'product', ['product_id'], ['id'])
        batch_op.drop_constraint('uq_item_name_number', type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_item_product_id_number'), ['product_id', 'number'])
        batch_op.drop_column('name')
        for column in MOVED:
            batch_op.drop_column(column)


def _items_to_products():
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, name, number, category, description, length_mm, width_mm, height_mm,"
        " created_at, updated_at FROM item ORDER BY number, id"
    )).mappings().all()

    # Categories, one per spelling ignoring case (the form already prevented
    # duplicates, but an import could have added some).
    categories = {}
    for row in rows:
        name = row["category"]
        if name and name.casefold() not in categories:
            conn.execute(sa.text("INSERT INTO category (name) VALUES (:name)"), {"name": name})
            categories[name.casefold()] = conn.execute(
                sa.text("SELECT id FROM category WHERE name = :name"), {"name": name}
            ).scalar_one()

    groups = {}
    for row in rows:
        groups.setdefault(row["name"].casefold(), []).append(row)

    for group in groups.values():
        first = group[0]  # lowest number: its spelling of the name is kept

        def known(field):
            # The first copy that has a value (they were all the same in practice).
            return next((r[field] for r in group if r[field] is not None), None)

        category = known("category")
        conn.execute(sa.text(
            "INSERT INTO product (name, category_id, description, length_mm, width_mm,"
            " height_mm, created_at, updated_at) VALUES (:name, :category_id,"
            " :description, :length_mm, :width_mm, :height_mm, :created_at, :updated_at)"
        ), {
            "name": first["name"],
            "category_id": categories[category.casefold()] if category else None,
            "description": known("description"),
            "length_mm": known("length_mm"),
            "width_mm": known("width_mm"),
            "height_mm": known("height_mm"),
            "created_at": min(r["created_at"] for r in group),
            "updated_at": max(r["updated_at"] for r in group),
        })
        product_id = conn.execute(
            sa.text("SELECT id FROM product WHERE name = :name"), {"name": first["name"]}
        ).scalar_one()

        # "Basler ace" #1 and "basler ace" #1 could both exist (only the
        # spelling told them apart); give clashing copies the next free number.
        used = set()
        for row in group:
            number = row["number"]
            if number in used:
                number = max(used) + 1
            used.add(number)
            conn.execute(
                sa.text("UPDATE item SET product_id = :p, number = :n WHERE id = :id"),
                {"p": product_id, "n": number, "id": row["id"]},
            )


def downgrade():
    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('category', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('length_mm', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('width_mm', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('height_mm', sa.Integer(), nullable=True))

    # Copy the product's details back onto each copy. Specs are lost.
    op.execute(
        "UPDATE item SET"
        " name = (SELECT name FROM product WHERE product.id = item.product_id),"
        " category = (SELECT category.name FROM product JOIN category"
        "   ON category.id = product.category_id WHERE product.id = item.product_id),"
        " description = (SELECT description FROM product WHERE product.id = item.product_id),"
        " length_mm = (SELECT length_mm FROM product WHERE product.id = item.product_id),"
        " width_mm = (SELECT width_mm FROM product WHERE product.id = item.product_id),"
        " height_mm = (SELECT height_mm FROM product WHERE product.id = item.product_id)"
    )

    with op.batch_alter_table('item', schema=None) as batch_op:
        batch_op.alter_column('name', existing_type=sa.String(length=100), nullable=False)
        batch_op.drop_constraint(batch_op.f('uq_item_product_id_number'), type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_item_name_number'), ['name', 'number'])
        batch_op.drop_constraint(batch_op.f('fk_item_product_id_product'), type_='foreignkey')
        batch_op.drop_column('product_id')

    op.drop_table('spec_value')
    op.drop_table('spec_option')
    op.drop_table('spec_field')
    op.drop_table('product')
    op.drop_table('category')
