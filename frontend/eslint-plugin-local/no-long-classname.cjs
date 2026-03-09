const MAX_INLINE_CLASSES = 2;

const MESSAGE =
  'Inline className with {{count}} utility classes (max {{max}}). ' +
  'Extract to a named constant in @mabi/shared/styles.';

function countClasses(str) {
  return str.trim().split(/\s+/).filter(Boolean).length;
}

module.exports = {
  meta: {
    type: 'suggestion',
    docs: {
      description: 'Warn when className has too many inline Tailwind classes',
    },
    schema: [
      {
        type: 'object',
        properties: {
          max: { type: 'integer', minimum: 1 },
        },
        additionalProperties: false,
      },
    ],
    messages: {
      tooMany: MESSAGE,
    },
  },

  create(context) {
    const max = (context.options[0] && context.options[0].max) || MAX_INLINE_CLASSES;

    function isClassNameAttr(node) {
      return (
        node.parent &&
        node.parent.type === 'JSXAttribute' &&
        node.parent.name &&
        node.parent.name.name === 'className'
      );
    }

    return {
      Literal(node) {
        if (typeof node.value !== 'string') return;
        if (!isClassNameAttr(node)) return;

        const count = countClasses(node.value);
        if (count > max) {
          context.report({
            node,
            messageId: 'tooMany',
            data: { count: String(count), max: String(max) },
          });
        }
      },

      TemplateLiteral(node) {
        const attr = node.parent;
        const expr = attr && attr.type === 'JSXExpressionContainer' ? attr : null;
        if (!expr || !isClassNameAttr(expr)) return;

        const staticClasses = node.quasis
          .map((q) => q.value.raw)
          .join(' ');
        const count = countClasses(staticClasses);
        if (count > max) {
          context.report({
            node,
            messageId: 'tooMany',
            data: { count: String(count), max: String(max) },
          });
        }
      },
    };
  },
};
