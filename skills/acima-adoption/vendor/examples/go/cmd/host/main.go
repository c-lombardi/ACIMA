// Command host is the composition root: the only place that knows every module.
package main

import (
	"fmt"

	catalogcontracts "acima.example/internal/catalog/contracts"
	catalog "acima.example/internal/catalog/impl"
	orderscontracts "acima.example/internal/orders/contracts"
	orders "acima.example/internal/orders/impl"
	payments "acima.example/internal/payments/impl"
)

func main() {
	cat := catalog.New()
	pay := payments.New(100_000)
	ord := orders.New(cat.Reader(), pay.Port())

	cat.Add(catalogcontracts.ProductView{
		ID: "p-1", Name: "Espresso beans", Price: catalogcontracts.MustMoney(1250, catalogcontracts.EUR),
	})
	cat.Add(catalogcontracts.ProductView{
		ID: "p-2", Name: "Filter papers", Price: catalogcontracts.MustMoney(320, catalogcontracts.EUR),
	})

	summary, rejected, err := ord.Place(orderscontracts.NewPlaceOrder("c-1", []orderscontracts.OrderLine{
		{ProductID: "p-1", UnitPrice: orderscontracts.MustMoney(1250, orderscontracts.EUR), Quantity: 2},
		{ProductID: "p-2", UnitPrice: orderscontracts.MustMoney(320, orderscontracts.EUR), Quantity: 1},
	}))
	if err != nil {
		panic(err)
	}
	if rejected != nil {
		fmt.Println("rejected:", rejected.Reason)
		return
	}

	fmt.Println("placed:", summary.ID, summary.Total.String())
	for _, event := range ord.Events() {
		switch event.(type) {
		case orderscontracts.Placed:
			fmt.Println("event: OrderPlaced")
		case orderscontracts.Rejected:
			fmt.Println("event: OrderRejected")
		}
	}
}
