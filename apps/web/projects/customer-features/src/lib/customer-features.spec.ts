import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CustomerFeatures } from './customer-features';

describe('CustomerFeatures', () => {
  let component: CustomerFeatures;
  let fixture: ComponentFixture<CustomerFeatures>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CustomerFeatures],
    }).compileComponents();

    fixture = TestBed.createComponent(CustomerFeatures);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
