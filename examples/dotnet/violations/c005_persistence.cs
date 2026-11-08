// acima-unit: payments.contracts
using Microsoft.EntityFrameworkCore;

namespace Acima.Payments.Contracts;

/// <summary>A contract that leaks the database.</summary>
public sealed record PaymentRow(DbContext Context);
