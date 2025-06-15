import React from 'react';
import ItemName from './ItemName';

const StatComparison = ({ stats }) => {
  if (!stats) return null;

  const entries = Object.entries(stats).filter(([, value]) => value !== 0);
  if (entries.length === 0) return null;

  return (
    <span className="stat-comparison">
      (
      {entries.map(([key, value], index) => {
        const isGood = value > 0;
        const sign = value > 0 ? '+' : '';
        const className = isGood ? 'stat-good' : 'stat-bad';
        const statName = key.replace(/_/g, ' ').toUpperCase();
        return (
          <React.Fragment key={key}>
            <span className={className}>{`${sign}${value} ${statName}`}</span>
            {index < entries.length - 1 && ', '}
          </React.Fragment>
        );
      })}
      )
    </span>
  );
};

const ShopListing = ({ data }) => {
  const { merchant_name, items } = data;

  const formatPrice = (copperValue) => {
    // Simple price formatting for now, can be expanded
    if (copperValue > 99) return `${Math.floor(copperValue / 100)}g ${copperValue % 100}c`;
    return `${copperValue}c`;
  };

  return (
    <div className="shop-listing-container">
      <div className="shop-header">--- {merchant_name}'s Wares ---</div>
      <div className="shop-items-table">
        <div className="shop-item-row header">
          <div className="item-name-col">Item</div>
          <div className="item-price-col">Price</div>
          <div className="item-comparison-col">Comparison vs. Equipped</div>
        </div>
        {items.map((item, index) => (
          <div key={item.id} className="shop-item-row">
            <div className="item-name-col">
              <span className="item-index">[{index + 1}]</span>
              <ItemName item={item} />
            </div>
            <div className="item-price-col">
              <span className="currency">{formatPrice(item.value)}</span>
            </div>
            <div className="item-comparison-col">
              {item.comparison_stats ? (
                <>
                  vs. {item.equipped_item_name} <StatComparison stats={item.comparison_stats} />
                </>
              ) : (
                <span className="no-comparison">—</span>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="shop-footer">Type <span className="command-suggestion">buy &lt;# or name&gt;</span> to purchase.</div>
    </div>
  );
};

export default ShopListing;