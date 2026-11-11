import React from 'react';
import AdjustmentsEditor from './AdjustmentsEditor';
import PercentGroups from './PercentGroups';
import { CostSection, LaborSection } from './DfpTable';
import { FieldsSection } from './FieldInputs';

export default function SchemaSection({ disabled, dfp, onChange, schema, section }) {
  const props = { disabled, dfp, onChange, section };
  switch (section.kind) {
    case 'labor-adjustments': return <AdjustmentsEditor {...props} />;
    case 'fields': return <FieldsSection {...props} schema={schema} />;
    case 'labor-table': return <LaborSection {...props} />;
    case 'cost-table': return <CostSection {...props} />;
    case 'percent-groups': return <PercentGroups {...props} />;
    default: return <p className="orc-note">Seção indisponível nesta versão do editor.</p>;
  }
}
